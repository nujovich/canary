# 🐤 Canary — Drift detection for AI agents

**Like a canary in the coal mine.** Before your agents go silent, Canary tells you something changed.

Framework-agnostic. Plugs into LangFuse, Tracepath, or any JSONL trace export. 4 detection methods. Prometheus + Grafana ready.

## ¿Qué detecta?

Los agentes AI no fallan de golpe — se degradan. Cambian cómo razonan, qué herramientas usan, qué caminos toman. Canary lo detecta antes del incidente.

| Método | Qué detecta | Técnica |
|---|---|---|
| **Embedding Drift** | Desviación semántica en el razonamiento | Cosine similarity vs baseline |
| **Tool Usage Drift** | Cambios en qué herramientas usa el agente | KL divergence |
| **Decision Path Drift** | Rutas de decisión diferentes | Índice de Jaccard |
| **LLM Judge** | Degradación en calidad de razonamiento | Cualquier LLM (OpenAI, Anthropic, Gemini, Ollama) |

## Instalación

```bash
pip install canary-drift
# o desde el repo:
git clone https://github.com/mermelada-tech/canary
cd canary
pip install -e .
```

## Uso rápido

```bash
# 1. Capturar baseline (semana "normal")
canary baseline --baseline-file semana_1.jsonl

# 2. Revisar drift
canary check --trace-file semana_2.jsonl

# 3. Métricas para Grafana
canary serve --port 9090
```

Output de `check`:
```json
{
  "embedding_drift": {"score": 0.08, "drifted": false},
  "tool_usage_drift": {"score": 0.12, "drifted": false},
  "decision_path_drift": {"score": 0.05, "drifted": false},
  "llm_judge": {"score": 4.3, "alert": false},
  "any_drifted": false
}
```

## Formato de datos

JSONL, un objeto por step:

```jsonl
{"run_id": "1", "step": 1, "reasoning": "Checking user balance...", "tool_name": "get_balance"}
{"run_id": "1", "step": 2, "reasoning": "Balance sufficient.", "tool_name": "transfer"}
```

Auto-detecta los campos: `reasoning`, `output`, `content`, `text` (razonamiento) y `tool_name`, `tool`, `name`, `action` (herramienta).

## Integraciones

```python
# LangFuse
from drift_detector.adapters.langfuse_adapter import LangFuseAdapter
adapter = LangFuseAdapter(public_key="...", secret_key="...")
data = adapter.fetch_traces(limit=200, hours_back=168)

# Tracepath (receipts firmados)
from drift_detector.adapters.tracepath_adapter import TracepathAdapter
adapter = TracepathAdapter("/var/tracepath/receipts")
data = adapter.load()

# Cualquier tool que exporte JSONL
canary baseline --baseline-file mis_traces.jsonl
canary check --trace-file mis_traces.jsonl
```

## LLM Judge — provider-agnostic

Auto-detection por variables de entorno:
```bash
export OPENAI_API_KEY="..."    # → OpenAI
export ANTHROPIC_API_KEY="..." # → Anthropic
export GEMINI_API_KEY="..."    # → Gemini (gratis)
export OLLAMA_HOST="..."       # → Ollama local
```

O explícito en código:
```python
from drift_detector.core.llm_judge import LLMJudge
judge = LLMJudge(provider="ollama", model="llama3.2")
```

## Métricas Prometheus + Dashboard Grafana

```bash
canary serve --port 9090
```

Importá `dashboards/grafana-drift-dashboard.json` en Grafana: status de drift, gauges por detector, LLM Judge score, auto-refresh 30s.

| Métrica | Descripción |
|---|---|
| `agent_drift_embedding_score` | Semantic drift (0-1) |
| `agent_drift_tool_usage_score` | Tool usage KL divergence (0-1) |
| `agent_drift_decision_path_score` | Decision path drift (0-1) |
| `agent_drift_llm_judge_score` | LLM judge quality (1-5) |
| `agent_drift_any_drifted` | 1 si algún detector disparó |

## ¿Por qué Canary?

Hay tracing (LangFuse, LangSmith). Hay anomaly detection para seguridad (ARMO). Hay drift para ML clásico (Arize). Pero **nadie te dice si tu agente está razonando peor que la semana pasada.** Hasta ahora.

Como el canario en la mina de carbón: cuando el canario cae, sabés que hay gas. Cuando Canary detecta drift, sabés que tu agente se está degradando.

## Licencia

MIT © 2026 Mermelada Tech