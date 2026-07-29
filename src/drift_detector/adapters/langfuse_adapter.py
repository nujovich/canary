"""LangFuse adapter: extract traces from LangFuse for drift detection."""

from typing import Dict, List


class LangFuseAdapter:
    """Pull traces from LangFuse and normalize them for the drift detectors.

    Outputs:
        reasoning_texts: List of concatenated reasoning chains
        tool_counts: Dict of tool name -> invocation count
        decision_paths: List of (tool1, tool2, ..., toolN) tuples
    """

    def __init__(self, public_key: str = "", secret_key: str = "", host: str = ""):
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host

    def fetch_traces(self, limit: int = 100, hours_back: int = 24) -> dict:
        """Fetch recent traces from LangFuse. Returns normalized format.

        Requires langfuse package: pip install langfuse
        """
        try:
            from langfuse import Langfuse
        except ImportError:
            raise ImportError("langfuse not installed. Run: pip install langfuse")

        client = Langfuse(
            public_key=self.public_key,
            secret_key=self.secret_key,
            host=self.host,
        )

        # Fetch traces (paginated, up to `limit`)
        traces = client.fetch_traces(limit=limit)

        reasoning_texts: List[str] = []
        tool_counts: Dict[str, int] = {}
        decision_paths: List[tuple[str, ...]] = []

        for trace in traces:
            path: List[str] = []
            reasoning_parts: List[str] = []

            for observation in trace.observations:
                if observation.type == "GENERATION":
                    output = observation.output or ""
                    reasoning_parts.append(output[:500])

                if observation.name and observation.name not in ("LLM Call", "Chat Completion"):
                    tool_counts[observation.name] = tool_counts.get(observation.name, 0) + 1
                    path.append(observation.name)

            if reasoning_parts:
                reasoning_texts.append(" | ".join(reasoning_parts))
            if path:
                decision_paths.append(tuple(path))

        return {
            "reasoning_texts": reasoning_texts,
            "tool_counts": tool_counts,
            "decision_paths": decision_paths,
            "total_traces": len(traces),
        }
