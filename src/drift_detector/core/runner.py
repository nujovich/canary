"""DriftRunner: orchestrates all detectors, exposes Prometheus metrics."""

from dataclasses import dataclass, field
from typing import Dict, List
from prometheus_client import Gauge, CollectorRegistry, generate_latest

from drift_detector.core.embedding_drift import EmbeddingDriftDetector
from drift_detector.core.tool_usage_drift import ToolUsageDriftDetector
from drift_detector.core.decision_path_drift import DecisionPathDriftDetector
from drift_detector.core.llm_judge import LLMJudge


@dataclass
class DriftReport:
    embedding_score: float = 0.0
    embedding_drifted: bool = False
    tool_usage_score: float = 0.0
    tool_usage_drifted: bool = False
    decision_path_score: float = 0.0
    decision_path_drifted: bool = False
    llm_judge_score: float | None = None
    llm_judge_alert: bool = False

    def any_drifted(self) -> bool:
        return self.embedding_drifted or self.tool_usage_drifted or self.decision_path_drifted

    def to_dict(self) -> dict:
        return {
            "embedding_drift": {"score": self.embedding_score, "drifted": self.embedding_drifted},
            "tool_usage_drift": {"score": self.tool_usage_score, "drifted": self.tool_usage_drifted},
            "decision_path_drift": {"score": self.decision_path_score, "drifted": self.decision_path_drifted},
            "llm_judge": {"score": self.llm_judge_score, "alert": self.llm_judge_alert},
            "any_drifted": self.any_drifted(),
        }


class DriftRunner:
    """Run all drift detectors against a batch of traces and export metrics."""

    def __init__(
        self,
        embedding_threshold: float = 0.15,
        tool_usage_threshold: float = 0.3,
        decision_path_threshold: float = 0.25,
        llm_sample_rate: float = 0.05,
        registry: CollectorRegistry | None = None,
    ):
        self.embedding = EmbeddingDriftDetector(threshold=embedding_threshold)
        self.tool_usage = ToolUsageDriftDetector(threshold=tool_usage_threshold)
        self.decision_path = DecisionPathDriftDetector(threshold=decision_path_threshold)
        self.llm_judge = LLMJudge(sample_rate=llm_sample_rate)

        self.registry = registry or CollectorRegistry()
        self._init_metrics()

    def _init_metrics(self):
        self.gauge_embedding = Gauge(
            "agent_drift_embedding_score",
            "Semantic drift score (0-1, lower is better)",
            registry=self.registry,
        )
        self.gauge_tool_usage = Gauge(
            "agent_drift_tool_usage_score",
            "Tool usage KL divergence score (0-1)",
            registry=self.registry,
        )
        self.gauge_decision_path = Gauge(
            "agent_drift_decision_path_score",
            "Decision path drift score (0-1)",
            registry=self.registry,
        )
        self.gauge_llm_judge = Gauge(
            "agent_drift_llm_judge_score",
            "LLM judge average quality score (1-5)",
            registry=self.registry,
        )
        self.gauge_any_drifted = Gauge(
            "agent_drift_any_drifted",
            "1 if any detector reports drift, 0 otherwise",
            registry=self.registry,
        )

    def set_baseline(
        self,
        reasoning_texts: List[str],
        tool_counts: Dict[str, int],
        decision_paths: List[tuple[str, ...]],
    ):
        """Capture baseline from a known-good period (e.g., first week)."""
        self.embedding.set_baseline(reasoning_texts)
        self.tool_usage.set_baseline(tool_counts)
        self.decision_path.set_baseline(decision_paths)

    def run(
        self,
        reasoning_texts: List[str],
        tool_counts: Dict[str, int],
        decision_paths: List[tuple[str, ...]],
    ) -> DriftReport:
        """Run all detectors and return a DriftReport."""
        emb_drifted, emb_score = self.embedding.is_drifted(reasoning_texts)
        tool_drifted, tool_score = self.tool_usage.is_drifted(tool_counts)
        path_drifted, path_score = self.decision_path.is_drifted(decision_paths)

        judge_result = self.llm_judge.rate_batch(reasoning_texts)

        report = DriftReport(
            embedding_score=emb_score,
            embedding_drifted=emb_drifted,
            tool_usage_score=tool_score,
            tool_usage_drifted=tool_drifted,
            decision_path_score=path_score,
            decision_path_drifted=path_drifted,
            llm_judge_score=judge_result["avg_score"],
            llm_judge_alert=judge_result["alert"],
        )

        self._update_metrics(report)
        return report

    def _update_metrics(self, report: DriftReport):
        self.gauge_embedding.set(report.embedding_score)
        self.gauge_tool_usage.set(report.tool_usage_score)
        self.gauge_decision_path.set(report.decision_path_score)
        if report.llm_judge_score is not None:
            self.gauge_llm_judge.set(report.llm_judge_score)
        self.gauge_any_drifted.set(1 if report.any_drifted() else 0)

    def metrics(self) -> bytes:
        """Return Prometheus text format metrics."""
        return generate_latest(self.registry)
