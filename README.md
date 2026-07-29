# 🧠 Agent Drift Detector

**Detect reasoning drift in AI agents** — open source, framework-agnostic, integrable with any observability tool.

## ¿Qué hace?

Los agentes AI se degradan silenciosamente. Cambian cómo razonan, qué herramientas usan, qué caminos toman. No es un error de código — es **drift**. Y tus herramientas de observabilidad actuales no lo ven.

Agent Drift Detector compara el comportamiento actual de tus agentes contra una baseline "saludable" usando 4 métodos:

| Método | Qué detecta | Técnica |
|---|---|---|
| **Embedding Drift** | Desviación semántica en el razonamiento | Cosine similarity vs baseline embeddings |
| **Tool Usage Drift** | Cambios en qué herramientas usa el agente | KL divergence en distribución de tool calls |
| **Decision Path Drift** | Rutas de decisión diferentes | Índice de Jaccard en secuencias de acciones |
| **LLM Judge** | Degradación en calidad de razonamiento | Cualquier LLM evalúa coherencia (OpenAI, Anthropic, Gemini, Ollama local) |

## Instalación

```bash
pip install agent-drift-detector
# o desde el repo:
git clone https://github.com/mermelada-tech/agent-drift-detector
cd agent-drift-detector
pip install -e .
```

## Uso rápido

### 1. Capturar baseline (semana "normal")

```bash
drift-detector baseline --baseline-file traces_week1.jsonl
```

### 2. Revisar drift contra baseline

```bash
drift-detector check --trace-file traces_week2.jsonl
```

Output:
```json
{
  "embedding_drift": {"score": 0.08, "drifted": false},
  "tool_usage_drift": {"score": 0.12, "drifted": false},
  "decision_path_drift": {"score": 0.05, "drifted": false},
  "llm_judge": {"score": 4.3, "alert": false},
  "any_drifted": false
}
```

### 3. Exponer métricas para Grafana

```bash
drift-detector serve --port 9090
```

Importá `dashboards/grafana-drift-dashboard.json` en Grafana.

## Formato de datos

Espera JSONL con un objeto por step:

```jsonl
{"run_id": "1", "step": 1, "reasoning": "Checking user balance...", "tool_name": "get_balance"}
{"run_id": "1", "step": 2, "reasoning": "Balance sufficient. Proceeding to transfer.", "tool_name": "transfer"}
{"run_id": "2", "step": 1, "reasoning": "Fetching customer profile...", "tool_name": "get_customer"}
```

Campos detectados automáticamente: `reasoning`, `output`, `content`, `text` (razonamiento) y `tool_name`, `tool`, `name`, `action` (herramienta).

## Integración con otras herramientas

### LangFuse

```python
from drift_detector.adapters.langfuse_adapter import LangFuseAdapter

adapter = LangFuseAdapter(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
)
data = adapter.fetch_traces(limit=200, hours_back=168)
```

### Tracepath

```python
from drift_detector.adapters.tracepath_adapter import TracepathAdapter

adapter = TracepathAdapter("/var/tracepath/receipts")
data = adapter.load()
# data["reasoning_texts"], data["tool_counts"], data["decision_paths"]
```

### Cualquier tool via JSONL

```bash
# Exportá tus traces a JSONL y usá el adapter genérico:
drift-detector baseline --baseline-file mis_traces.jsonl
drift-detector check --trace-file mis_traces_semana_2.jsonl
```

## Métricas de Prometheus

| Métrica | Descripción |
|---|---|
| `agent_drift_embedding_score` | Semantic drift (0-1) |
| `agent_drift_tool_usage_score` | Tool usage KL divergence (0-1) |
| `agent_drift_decision_path_score` | Decision path drift (0-1) |
| `agent_drift_llm_judge_score` | LLM judge quality (1-5) |
| `agent_drift_any_drifted` | 1 if any detector triggered |

## Dashboard de Grafana

Importá `dashboards/grafana-drift-dashboard.json` en tu Grafana. Incluye:

- 🟢🔴 Status de drift general
- Gauges para cada detector con thresholds configurables
- LLM Judge score
- Auto-refresh cada 30s

![Grafana Dashboard](dashboards/dashboard-preview.png)

## ¿Por qué esto no existe?

Hay tracing (LangFuse, LangSmith). Hay anomaly detection para seguridad (ARMO). Hay drift para ML clásico (Arize, Evidently). Pero **nadie te dice si tu agente está razonando peor que la semana pasada**. Hasta ahora.

## Stack

- **Python 3.10+**
- **sentence-transformers** — embeddings para semantic drift
- **scipy** — KL divergence para tool usage drift
- **prometheus-client** — métricas para Grafana
- **click** — CLI
- **Cualquier LLM** — OpenAI GPT-4o-mini, Anthropic Claude Haiku, Gemini Flash (gratis), Ollama local, o cualquier endpoint OpenAI-compatible

## Contribuir

```bash
git clone https://github.com/mermelada-tech/agent-drift-detector
cd agent-drift-detector
pip install -e ".[dev]"
pytest
```

## Licencia

MIT © 2026 Mermelada Tech
