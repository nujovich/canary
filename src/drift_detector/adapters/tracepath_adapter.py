"""Tracepath adapter: read signed receipts for drift detection.

Tracepath stores audit receipts as signed JSON records with hash-chaining.
This adapter reads them and normalizes the format for the drift detectors.
"""

import json
import glob
from typing import Dict, List
from pathlib import Path


class TracepathAdapter:
    """Read Tracepath audit receipts and normalize for drift detection.

    Receipts have the format:
    {
        "receipt_hash": "sha256:...",
        "previous_hash": "...",
        "step": {...},
        "reasoning": "...",
        "tool_call": {"tool": "...", "arguments_hash": "..."},
        "signature": "ed25519:..."
    }
    """

    def __init__(self, receipts_dir: str, glob_pattern: str = "*.jsonl"):
        self.receipts_dir = Path(receipts_dir)
        self.glob_pattern = glob_pattern

    def _load_receipts_jsonl(self) -> List[dict]:
        """Load all receipts from JSONL files in the directory."""
        receipts = []
        for filepath in self.receipts_dir.glob(self.glob_pattern):
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        receipts.append(json.loads(line))
        return receipts

    def _load_receipts_json(self) -> List[dict]:
        """Load all receipts from individual JSON files."""
        receipts = []
        for filepath in self.receipts_dir.glob(self.glob_pattern):
            with open(filepath) as f:
                receipts.append(json.load(f))
        return receipts

    def load(self) -> dict:
        """Load receipts and normalize into drift detector format.

        Tries JSONL first, then falls back to individual JSON files.
        """
        try:
            receipts = self._load_receipts_jsonl()
            if not receipts:
                receipts = self._load_receipts_json()
        except Exception:
            receipts = self._load_receipts_json()

        reasoning_texts: List[str] = []
        tool_counts: Dict[str, int] = {}
        decision_paths: List[tuple[str, ...]] = []

        # Group by run_id to build paths
        runs: Dict[str, List[dict]] = {}
        for r in receipts:
            run_id = r.get("run_id", "unknown")
            runs.setdefault(run_id, []).append(r)

        for run_id, steps in runs.items():
            path: List[str] = []
            reasoning_parts: List[str] = []

            for step in steps:
                reasoning = step.get("reasoning", "") or step.get("step", {}).get("reasoning", "")
                if reasoning:
                    reasoning_parts.append(str(reasoning)[:500])

                tool = step.get("tool_call", {})
                if isinstance(tool, dict):
                    tool_name = tool.get("tool", "") or tool.get("name", "")
                else:
                    tool_name = str(tool)
                if tool_name:
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                    path.append(tool_name)

            if reasoning_parts:
                reasoning_texts.append(" | ".join(reasoning_parts))
            if path:
                decision_paths.append(tuple(path))

        return {
            "reasoning_texts": reasoning_texts,
            "tool_counts": tool_counts,
            "decision_paths": decision_paths,
            "total_receipts": len(receipts),
            "total_runs": len(runs),
        }
