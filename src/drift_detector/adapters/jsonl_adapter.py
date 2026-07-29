"""JSONL adapter: generic adapter for any tool that exports traces as JSONL."""

import json
from typing import Dict, List
from pathlib import Path


class JSONLAdapter:
    """Read generic JSONL traces and normalize for drift detection.

    Expected JSONL format (one JSON object per line):
    {
        "run_id": "uuid",
        "step": 1,
        "reasoning": "...",
        "tool_name": "...",
        ...
    }

    Also supports LangFuse-exported JSONL and Arize-exported JSONL
    with automatic field detection.
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)

    def load(self) -> dict:
        """Load JSONL and normalize into drift detector format."""
        traces = []
        with open(self.filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(json.loads(line))

        reasoning_texts: List[str] = []
        tool_counts: Dict[str, int] = {}
        decision_paths: List[tuple[str, ...]] = []

        # Group by run_id
        runs: Dict[str, List[dict]] = {}
        for t in traces:
            run_id = t.get("run_id") or t.get("trace_id") or t.get("session_id", "unknown")
            runs.setdefault(run_id, []).append(t)

        for run_id, steps in runs.items():
            path: List[str] = []
            reasoning_parts: List[str] = []

            for step in steps:
                # Auto-detect reasoning field
                reasoning = (
                    step.get("reasoning")
                    or step.get("output")
                    or step.get("content")
                    or step.get("text")
                    or ""
                )
                if reasoning:
                    reasoning_parts.append(str(reasoning)[:500])

                # Auto-detect tool name field
                tool_name = (
                    step.get("tool_name")
                    or step.get("tool")
                    or step.get("name")
                    or step.get("action")
                    or ""
                )
                if tool_name:
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                    path.append(str(tool_name))

            if reasoning_parts:
                reasoning_texts.append(" | ".join(reasoning_parts))
            if path:
                decision_paths.append(tuple(path))

        return {
            "reasoning_texts": reasoning_texts,
            "tool_counts": tool_counts,
            "decision_paths": decision_paths,
            "total_traces": len(traces),
            "total_runs": len(runs),
        }
