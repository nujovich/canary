"""Goal drift detection: compare distribution of agent goals/tasks.

Distinguishes between:
- Input drift: the goals changed (new brief, different priorities) → expected
- Degradation drift: same goals, different behavior → alarm
"""

from collections import Counter
from typing import Dict, List
from scipy.stats import entropy


class GoalDriftDetector:
    """Detect if the distribution of agent goals has shifted.

    If the goals changed significantly, any behavior drift is likely
    legitimate adaptation, not degradation.
    """

    def __init__(self, threshold: float = 0.3, smoothing: float = 0.01):
        self.threshold = threshold
        self.smoothing = smoothing
        self.baseline_dist: Dict[str, float] | None = None

    def _normalize(self, counts: Dict[str, int]) -> Dict[str, float]:
        if not counts:
            return {}
        total = sum(counts.values())
        return {t: (c / total) + self.smoothing for t, c in counts.items()}

    def _align(self, p: Dict[str, float], q: Dict[str, float]) -> tuple[List[float], List[float]]:
        all_keys = sorted(set(p) | set(q))
        return (
            [p.get(k, self.smoothing) for k in all_keys],
            [q.get(k, self.smoothing) for k in all_keys],
        )

    def set_baseline(self, goal_counts: Dict[str, int]) -> None:
        self.baseline_dist = self._normalize(goal_counts)

    def score(self, current_counts: Dict[str, int]) -> float:
        if self.baseline_dist is None:
            raise ValueError("Baseline not set. Call set_baseline() first.")
        current_dist = self._normalize(current_counts)
        p, q = self._align(self.baseline_dist, current_dist)
        kl_pq = entropy(p, q)
        kl_qp = entropy(q, p)
        return min(1.0, float((kl_pq + kl_qp) / 2))

    def is_drifted(self, current_counts: Dict[str, int]) -> tuple[bool, float]:
        score = self.score(current_counts)
        return score > self.threshold, score
