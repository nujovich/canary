"""Decision path drift: detect when the agent takes different routes."""

from typing import Dict, List
from collections import Counter


class DecisionPathDriftDetector:
    """Compare the topology of agent decision paths against a baseline.

    Each path is a tuple of (step1_action, step2_action, ..., stepN_action).
    Detects when the agent starts taking different routes through tasks
    — same endpoint, different reasoning.
    """

    def __init__(self, threshold: float = 0.25):
        self.threshold = threshold
        self.baseline_paths: Counter | None = None

    def set_baseline(self, paths: List[tuple[str, ...]]) -> None:
        """Set baseline paths (e.g., from first week in production)."""
        self.baseline_paths = Counter(paths)

    def score(self, current_paths: List[tuple[str, ...]]) -> float:
        """Return drift score based on path distribution overlap.

        Jaccard-like similarity between path distributions.
        0 = identical paths, 1 = completely different.
        """
        if self.baseline_paths is None:
            raise ValueError("Baseline not set. Call set_baseline() first.")

        current_counter = Counter(current_paths)
        all_paths = set(self.baseline_paths) | set(current_counter)

        if not all_paths:
            return 0.0

        intersection = sum(
            min(self.baseline_paths.get(p, 0), current_counter.get(p, 0))
            for p in all_paths
        )
        union = sum(
            max(self.baseline_paths.get(p, 0), current_counter.get(p, 0))
            for p in all_paths
        )

        if union == 0:
            return 0.0

        jaccard = intersection / union
        return round(float(1 - jaccard), 4)

    def is_drifted(self, current_paths: List[tuple[str, ...]]) -> tuple[bool, float]:
        """Return (drifted_bool, score)."""
        score = self.score(current_paths)
        return score > self.threshold, score
