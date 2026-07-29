# 🐤 Canary — Drift detection for AI agents

**Like a canary in the coal mine.** Before your agents go silent, Canary tells you something changed.

Framework-agnostic. Plugs into LangFuse, Tracepath, or any JSONL trace export. 4 detection methods. Prometheus + Grafana ready.

## What it detects

AI agents don't fail suddenly — they degrade. They change how they reason, which tools they call, and what paths they take through tasks. Canary catches it before it becomes an incident.

| Method | What it catches | Technique |
|---|---|---|
| **Embedding Drift** | Semantic deviation in reasoning | Cosine similarity vs baseline |
| **Tool Usage Drift** | Agent starts calling different tools | KL divergence on tool distribution |
| **Decision Path Drift** | Different routes through the same tasks | Jaccard index on action sequences |
| **LLM Judge** | Reasoning quality degradation | Any LLM scores coherence (OpenAI, Anthropic, Gemini, Ollama) |

## Install

```bash
pip install canary-drift
# or from source:
git clone https://github.com/nujovich/canary
cd canary
pip install -e .
```

## Quick start

```bash
# 1. Capture a baseline from a known-good week
canary baseline --baseline-file week_1.jsonl

# 2. Check current traces for drift
canary check --trace-file week_2.jsonl

# 3. Serve Prometheus metrics for Grafana
canary serve --port 9090
```

Example `check` output:
```json
{
  "embedding_drift": {"score": 0.08, "drifted": false},
  "tool_usage_drift": {"score": 0.12, "drifted": false},
  "decision_path_drift": {"score": 0.05, "drifted": false},
  "llm_judge": {"score": 4.3, "alert": false},
  "any_drifted": false
}
```

## Trace format

JSONL — one JSON object per agent step:

```jsonl
{"run_id": "1", "step": 1, "reasoning": "Checking user balance...", "tool_name": "get_balance"}
{"run_id": "1", "step": 2, "reasoning": "Balance sufficient.", "tool_name": "transfer"}
```

Field names are auto-detected: `reasoning`, `output`, `content`, or `text` for reasoning, and `tool_name`, `tool`, `name`, or `action` for tool calls.

## Integrations

```python
# LangFuse
from drift_detector.adapters.langfuse_adapter import LangFuseAdapter
adapter = LangFuseAdapter(public_key="...", secret_key="...")
data = adapter.fetch_traces(limit=200, hours_back=168)

# Tracepath (signed receipts)
from drift_detector.adapters.tracepath_adapter import TracepathAdapter
adapter = TracepathAdapter("/var/tracepath/receipts")
data = adapter.load()

# Any tool via JSONL export
canary baseline --baseline-file my_traces.jsonl
canary check --trace-file my_traces.jsonl
```

## LLM Judge — provider-agnostic

Auto-detection via environment variables:
```bash
export OPENAI_API_KEY="..."    # → OpenAI
export ANTHROPIC_API_KEY="..." # → Anthropic
export GEMINI_API_KEY="..."    # → Gemini (free tier)
export OLLAMA_HOST="..."       # → Ollama (local)
```

Or explicit in Python:
```python
from drift_detector.core.llm_judge import LLMJudge
judge = LLMJudge(provider="ollama", model="llama3.2")
```

## Prometheus metrics + Grafana dashboard

```bash
canary serve --port 9090
```

Import `dashboards/grafana-drift-dashboard.json` into Grafana: drift status, per-detector gauges with configurable thresholds, LLM Judge score, 30s auto-refresh.

| Metric | Description |
|---|---|
| `agent_drift_embedding_score` | Semantic drift (0-1, lower is better) |
| `agent_drift_tool_usage_score` | Tool usage KL divergence (0-1) |
| `agent_drift_decision_path_score` | Decision path drift (0-1) |
| `agent_drift_llm_judge_score` | LLM judge quality (1-5) |
| `agent_drift_any_drifted` | 1 if any detector triggered |

## Why Canary?

Tracing exists. Anomaly detection for security exists. ML model drift detection exists. But **nobody tells you whether your agent is reasoning worse this week than last week.** Until now.

Like the canary in the coal mine: when the bird stops singing, you know there's gas. When Canary flags drift, you know your agents are degrading — before your users do.

## License

MIT © 2026 Mermelada Tech