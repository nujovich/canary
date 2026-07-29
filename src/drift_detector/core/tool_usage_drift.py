"""Tool usage drift: detect shifts in which tools the agent calls."""

from collections import Counter
from typing import Dict, List
from scipy.stats import entropy


class ToolUsageDriftDetector:
    """Detect drift in tool usage distribution using KL divergence.

    If the agent starts calling different tools than it used to — or the same
    tools in different proportions — this detector catches it.
    """

    def __init__(self, threshold: float = 0.3, smoothing: float = 0.01):
        self.threshold = threshold
        self.smoothing = smoothing
        self.baseline_dist: Dict[str, float] | None = None
        self._all_tools: set[str] = set()

    def _normalize(self, tool_counts: Dict[str, int]) -> Dict[str, float]:
        """Convert counts to probability distribution with smoothing."""
        if not tool_counts:
            return {}
        total = sum(tool_counts.values())
        return {t: (c / total) + self.smoothing for t, c in tool_counts.items()}

    def _align_distributions(self, dist_p: Dict[str, float], dist_q: Dict[str, float]) -> tuple[List[float], List[float]]:
        """Align two distributions to the same set of keys."""
        all_keys = sorted(set(dist_p) | set(dist_q))
        p = [dist_p.get(k, self.smoothing) for k in all_keys]
        q = [dist_q.get(k, self.smoothing) for k in all_keys]
        return p, q

    def set_baseline(self, tool_counts: Dict[str, int]) -> None:
        """Set baseline from tool usage counts (e.g., first week in production)."""
        self.baseline_dist = self._normalize(tool_counts)

    def score(self, current_counts: Dict[str, int]) -> float:
        """Return drift score via symmetric KL divergence."""
        if self.baseline_dist is None:
            raise ValueError("Baseline not set. Call set_baseline() first.")

        current_dist = self._normalize(current_counts)
        p, q = self._align_distributions(self.baseline_dist, current_dist)

        kl_pq = entropy(p, q)
        kl_qp = entropy(q, p)
        symmetric_kl = (kl_pq + kl_qp) / 2

        return min(1.0, float(symmetric_kl))

    def is_drifted(self, current_counts: Dict[str, int]) -> tuple[bool, float]:
        """Return (drifted_bool, score)."""
        score = self.score(current_counts)
        return score > self.threshold, score
