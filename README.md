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

## Roadmap

Canary is being built in the open to become the go-to drift detection tool for AI agent teams. Each milestone delivers a single, concrete capability that teams can adopt immediately.

### v0.2 — CI/CD & Native Integrations 🚧

**Goal:** One `uses:` line in a GitHub Actions workflow and Canary runs drift checks on every deploy.

| Deliverable | What it unlocks |
|---|---|
| **GitHub Action** (`nujovich/canary@v1`) | `fail-on: degradation_drift` blocks merges when agent quality degrades |
| **Baseline as JSON** (no pickle) | Version-controlled baselines in git — compare against the previous release, not "N weeks ago" |
| **Hermes Telemetry adapter** | Read directly from `telemetry.db` — no manual JSONL export for Hermes users |
| PR comment report | Drift table posted as a review comment on the PR that triggered the check |

```yaml
# .github/workflows/canary.yml
- uses: nujovich/canary@v1
  with:
    source: hermes-telemetry
    jobs: BUILD,WATCH,PULSE
    baseline-ref: ${{ github.event.before }}
    fail-on: degradation_drift
```

### v0.3 — Native LangFuse + Human-Readable Reports

**Goal:** Teams using LangFuse (the de-facto standard for agent tracing) get drift detection with zero configuration. PMs and stakeholders can read the output.

| Deliverable | What it unlocks |
|---|---|
| **LangFuse native adapter** | `canary check --source langfuse` — no JSONL export, reads traces directly |
| **`canary report --format md`** | Markdown table output for pasting into issues, PRs, Slack, Notion |
| **CI summary annotation** | GitHub Actions step summary with visual drift table |

### v0.4 — Self-Contained Dashboard

**Goal:** Small teams get a visual drift dashboard without setting up Grafana + Prometheus.

| Deliverable | What it unlocks |
|---|---|
| **Standalone web dashboard** | `canary serve --dashboard` — single-page HTML with drift history and per-job health |
| **OpenTelemetry adapter** | Cover everything else: Arize, Phoenix, Datadog, any OTLP sink |
| **Job health overview** | Green/yellow/red status per monitored agent, 30-day drift trend |

### v1.0 — Multi-Team Ready

**Goal:** Workspaces, team-level baselines, and alerting — the tool grows with the org.

| Deliverable | What it unlocks |
|---|---|
| **Workspaces** | Per-team baselines, thresholds, and dashboards under one Canary instance |
| **Slack / Discord / Telegram alerts** | Push notifications when drift is detected, not just CI failures |
| **Baseline suggestions** | `canary baseline --auto` — picks the best window automatically |
| **Drift explainability** | "Why did this drift?" — highlights which tool sequences or reasoning patterns changed |

### Beyond v1.0

- **Multi-model comparison** — compare the same task across GPT-4o, Claude, Gemini, and open-source models
- **A/B test mode** — run two agent versions side by side and detect which one drifts less
- **Plugin system** — community detectors (safety drift, hallucination rate, latency drift)
- **Managed cloud** — hosted Canary for teams that don't want to self-host

---

## License

MIT © 2026 Mermelada Tech