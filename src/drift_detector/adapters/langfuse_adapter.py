"""LangFuse adapter: extract traces from LangFuse for drift detection.

Uses the LangFuse REST API (no SDK dependency) so it works with any
LangFuse version — self-hosted, cloud, or OSS.

Configuration via environment variables:
  LANGFUSE_PUBLIC_KEY  — public key (pk-lf-...)
  LANGFUSE_SECRET_KEY  — secret key (sk-lf-...)
  LANGFUSE_HOST        — base URL (default: https://cloud.langfuse.com)
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from urllib.parse import quote
from typing import Dict, List


class LangFuseAdapter:
    """Pull traces from LangFuse REST API and normalize for drift detectors.

    Filters by trace name (e.g. agent job name) and time range.
    """

    DEFAULT_HOST = "https://cloud.langfuse.com"

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        host: str = "",
        trace_name: str = "",
        hours_back: int = 168,
        limit: int = 200,
    ):
        self.public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        self.host = (host or os.environ.get("LANGFUSE_HOST", self.DEFAULT_HOST)).rstrip("/")
        self.trace_name = trace_name
        self.hours_back = hours_back
        self.limit = limit

    def _auth_header(self) -> str:
        """Basic auth with public_key:secret_key."""
        raw = f"{self.public_key}:{self.secret_key}"
        return "Basic " + base64.b64encode(raw.encode()).decode()

    def _get(self, path: str) -> dict:
        """GET a LangFuse API endpoint with pagination."""
        url = f"{self.host}{path}"
        req = urllib.request.Request(url, headers={"Authorization": self._auth_header()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def fetch_traces(self) -> dict:
        """Fetch recent traces matching trace_name and normalize.

        Returns dict with reasoning_texts, tool_counts, decision_paths,
        total_traces, total_runs — the standard format consumed by DriftRunner.
        """
        from datetime import datetime, timezone, timedelta

        since = (datetime.now(timezone.utc) - timedelta(hours=self.hours_back)).isoformat()

        params = []
        if self.trace_name:
            params.append(f"name={urllib.request.quote(self.trace_name)}")
        params.append(f"limit={self.limit}")

        path = f"/api/public/traces?{'&'.join(params)}"
        data = self._get(path)

        traces = data.get("data", [])
        if not traces:
            return self._empty_result()

        reasoning_texts: List[str] = []
        tool_counts: Dict[str, int] = {}
        decision_paths: List[tuple[str, ...]] = []

        for trace in traces:
            # Fetch observations for this trace
            trace_id = trace["id"]
            obs = self._get_observations(trace_id)

            path_steps: List[str] = []
            reasoning_parts: List[str] = []

            for o in obs:
                otype = o.get("type", "")
                name = o.get("name", "")

                # GENERATION = LLM call — extract reasoning
                if otype == "GENERATION":
                    output = o.get("output") or ""
                    if output:
                        reasoning_parts.append(str(output)[:500])

                # SPAN = tool call / agent step
                if otype == "SPAN" and name:
                    tool_counts[name] = tool_counts.get(name, 0) + 1
                    path_steps.append(name)

            if reasoning_parts:
                reasoning_texts.append(" | ".join(reasoning_parts))
            if path_steps:
                decision_paths.append(tuple(path_steps))

        return {
            "reasoning_texts": reasoning_texts,
            "tool_counts": tool_counts,
            "decision_paths": decision_paths,
            "total_traces": len(traces),
            "total_runs": len(reasoning_texts),
            "source": "langfuse",
        }

    def _get_observations(self, trace_id: str) -> list:
        """Fetch all observations for a trace."""
        try:
            path = f"/api/public/observations?traceId={trace_id}&limit=500"
            data = self._get(path)
            return data.get("data", [])
        except Exception:
            return []

    def _empty_result(self) -> dict:
        return {
            "reasoning_texts": [],
            "tool_counts": {},
            "decision_paths": [],
            "total_traces": 0,
            "total_runs": 0,
            "source": "langfuse",
        }