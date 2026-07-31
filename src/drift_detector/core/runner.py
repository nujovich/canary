"""DriftRunner: orchestrates all detectors, classifies drift type, exports Prometheus metrics."""

from dataclasses import dataclass, field
from typing import Dict, List
from prometheus_client import Gauge, CollectorRegistry, generate_latest

from drift_detector.core.embedding_drift import EmbeddingDriftDetector
from drift_detector.core.tool_usage_drift import ToolUsageDriftDetector
from drift_detector.core.decision_path_drift import DecisionPathDriftDetector
from drift_detector.core.goal_drift import GoalDriftDetector
from drift_detector.core.llm_judge import LLMJudge


@dataclass
class DriftReport:
    goal_score: float = 0.0
    goal_drifted: bool = False
    embedding_score: float = 0.0
    embedding_drifted: bool = False
    tool_usage_score: float = 0.0
    tool_usage_drifted: bool = False
    decision_path_score: float = 0.0
    decision_path_drifted: bool = False
    llm_judge_score: float | None = None
    llm_judge_alert: bool = False

    # Classification: distinguishes input drift from degradation
    drift_type: str = "none"  # "none" | "input_drift" | "degradation_drift"

    def any_drifted(self) -> bool:
        return self.embedding_drifted or self.tool_usage_drifted or self.decision_path_drifted

    def to_dict(self) -> dict:
        return {
            "goal_drift": {"score": self.goal_score, "drifted": self.goal_drifted},
            "embedding_drift": {"score": self.embedding_score, "drifted": self.embedding_drifted},
            "tool_usage_drift": {"score": self.tool_usage_score, "drifted": self.tool_usage_drifted},
            "decision_path_drift": {"score": self.decision_path_score, "drifted": self.decision_path_drifted},
            "llm_judge": {"score": self.llm_judge_score, "alert": self.llm_judge_alert},
            "any_drifted": self.any_drifted(),
            "drift_type": self.drift_type,
        }


class DriftRunner:
    """Run all drift detectors and classify the type of drift.

    Classification:
    - input_drift: goals changed AND behavior changed → expected, not a bug
    - degradation_drift: goals did NOT change but behavior did → alarm
    - none: no significant drift detected
    """

    def __init__(
        self,
        goal_threshold: float = 0.3,
        embedding_threshold: float = 0.15,
        tool_usage_threshold: float = 0.3,
        decision_path_threshold: float = 0.25,
        llm_sample_rate: float = 0.05,
        registry: CollectorRegistry | None = None,
    ):
        self.goal = GoalDriftDetector(threshold=goal_threshold)
        self.embedding = EmbeddingDriftDetector(threshold=embedding_threshold)
        self.tool_usage = ToolUsageDriftDetector(threshold=tool_usage_threshold)
        self.decision_path = DecisionPathDriftDetector(threshold=decision_path_threshold)
        self.llm_judge = LLMJudge(sample_rate=llm_sample_rate)

        self.registry = registry or CollectorRegistry()
        self._init_metrics()

    def _init_metrics(self):
        self.gauge_goal = Gauge(
            "agent_drift_goal_score", "Goal distribution drift (0-1)", registry=self.registry
        )
        self.gauge_embedding = Gauge(
            "agent_drift_embedding_score", "Semantic drift score (0-1)", registry=self.registry
        )
        self.gauge_tool_usage = Gauge(
            "agent_drift_tool_usage_score", "Tool usage KL divergence (0-1)", registry=self.registry
        )
        self.gauge_decision_path = Gauge(
            "agent_drift_decision_path_score", "Decision path drift (0-1)", registry=self.registry
        )
        self.gauge_llm_judge = Gauge(
            "agent_drift_llm_judge_score", "LLM judge quality (1-5)", registry=self.registry
        )
        self.gauge_any_drifted = Gauge(
            "agent_drift_any_drifted", "1 if any detector triggered", registry=self.registry
        )
        self.gauge_drift_type = Gauge(
            "agent_drift_type",
            "Drift classification: 0=none, 1=input_drift, 2=degradation_drift",
            registry=self.registry,
        )

    def set_baseline(
        self,
        goal_counts: Dict[str, int] | None = None,
        reasoning_texts: List[str] | None = None,
        tool_counts: Dict[str, int] | None = None,
        decision_paths: List[tuple[str, ...]] | None = None,
    ):
        """Capture baseline from a known-good period."""
        if goal_counts:
            self.goal.set_baseline(goal_counts)
        if reasoning_texts:
            self.embedding.set_baseline(reasoning_texts)
        if tool_counts:
            self.tool_usage.set_baseline(tool_counts)
        if decision_paths:
            self.decision_path.set_baseline(decision_paths)

    def run(
        self,
        goal_counts: Dict[str, int] | None = None,
        reasoning_texts: List[str] | None = None,
        tool_counts: Dict[str, int] | None = None,
        decision_paths: List[tuple[str, ...]] | None = None,
    ) -> DriftReport:
        """Run all detectors and classify drift type."""
        report = DriftReport()

        # Detect goal drift (did the input change?)
        if goal_counts and self.goal.baseline_dist:
            report.goal_drifted, report.goal_score = self.goal.is_drifted(goal_counts)

        # Detect behavior drift
        if reasoning_texts and self.embedding.baseline_embeddings is not None:
            report.embedding_drifted, report.embedding_score = self.embedding.is_drifted(reasoning_texts)
        if tool_counts and self.tool_usage.baseline_dist:
            report.tool_usage_drifted, report.tool_usage_score = self.tool_usage.is_drifted(tool_counts)
        if decision_paths and self.decision_path.baseline_paths:
            report.decision_path_drifted, report.decision_path_score = self.decision_path.is_drifted(decision_paths)

        # LLM judge
        if reasoning_texts:
            judge_result = self.llm_judge.rate_batch(reasoning_texts)
            report.llm_judge_score = judge_result["avg_score"]
            report.llm_judge_alert = judge_result["alert"]

        # Classify drift type
        report.drift_type = self._classify(report)

        self._update_metrics(report)
        return report

    def _classify(self, report: DriftReport) -> str:
        """Classify drift: input_drift vs degradation_drift vs none."""
        behavior_drifted = report.any_drifted()

        if not behavior_drifted:
            return "none"

        if report.goal_drifted:
            # Goals changed AND behavior changed → likely legitimate
            return "input_drift"
        else:
            # Same goals, different behavior → degradation alarm
            return "degradation_drift"

    def _update_metrics(self, report: DriftReport):
        self.gauge_goal.set(report.goal_score)
        self.gauge_embedding.set(report.embedding_score)
        self.gauge_tool_usage.set(report.tool_usage_score)
        self.gauge_decision_path.set(report.decision_path_score)
        if report.llm_judge_score is not None:
            self.gauge_llm_judge.set(report.llm_judge_score)
        self.gauge_any_drifted.set(1 if report.any_drifted() else 0)
        type_map = {"none": 0, "input_drift": 1, "degradation_drift": 2}
        self.gauge_drift_type.set(type_map.get(report.drift_type, 0))

    def metrics(self) -> bytes:
        """Return Prometheus text format metrics."""
        return generate_latest(self.registry)
