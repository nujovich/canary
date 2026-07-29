"""Example: basic usage of agent-drift-detector."""

# ------------------------------------------------------------
# 1. SETUP: install the package
#    pip install -e .
# ------------------------------------------------------------

# ------------------------------------------------------------
# 2. BASELINE: capture a week of "normal" behavior
#
#    drift-detector baseline --baseline-file traces_week1.jsonl
#
#    Your JSONL should look like:
#    {"run_id": "1", "step": 1, "reasoning": "...", "tool_name": "get_customer"}
#    {"run_id": "1", "step": 2, "reasoning": "...", "tool_name": "check_balance"}
#    {"run_id": "2", "step": 1, "reasoning": "...", "tool_name": "get_customer"}
# ------------------------------------------------------------

# ------------------------------------------------------------
# 3. CHECK: compare current week against baseline
#
#    drift-detector check --trace-file traces_week2.jsonl
#
#    Output:
#    {
#      "embedding_drift": {"score": 0.08, "drifted": false},
#      "tool_usage_drift": {"score": 0.12, "drifted": false},
#      "decision_path_drift": {"score": 0.05, "drifted": false},
#      "llm_judge": {"score": 4.3, "alert": false},
#      "any_drifted": false
#    }
# ------------------------------------------------------------

# ------------------------------------------------------------
# 4. SERVE: start Prometheus endpoint for Grafana
#
#    drift-detector serve --port 9090
#
#    Then import dashboards/grafana-drift-dashboard.json into Grafana.
# ------------------------------------------------------------

# ------------------------------------------------------------
# 5. PROGRAMMATIC: use in Python
# ------------------------------------------------------------
def example_programmatic():
    from drift_detector.adapters.jsonl_adapter import JSONLAdapter
    from drift_detector.core.runner import DriftRunner

    # Load data
    baseline_adapter = JSONLAdapter("traces_week1.jsonl")
    baseline_data = baseline_adapter.load()

    current_adapter = JSONLAdapter("traces_week2.jsonl")
    current_data = current_adapter.load()

    # Set baseline and run
    runner = DriftRunner()
    runner.set_baseline(
        reasoning_texts=baseline_data["reasoning_texts"],
        tool_counts=baseline_data["tool_counts"],
        decision_paths=baseline_data["decision_paths"],
    )

    report = runner.run(
        reasoning_texts=current_data["reasoning_texts"],
        tool_counts=current_data["tool_counts"],
        decision_paths=current_data["decision_paths"],
    )

    print(report.to_dict())

    # Export Prometheus metrics
    print(runner.metrics().decode())


# ------------------------------------------------------------
# 6. INTEGRATION: with Tracepath
# ------------------------------------------------------------
def example_tracepath():
    from drift_detector.adapters.tracepath_adapter import TracepathAdapter
    from drift_detector.core.runner import DriftRunner

    adapter = TracepathAdapter("/var/tracepath/receipts")
    data = adapter.load()
    print(f"Loaded {data['total_receipts']} receipts from {data['total_runs']} runs")

    runner = DriftRunner()

    # First week as baseline
    first_week = {k: v for k, v in data.items() if k != "total_receipts" and k != "total_runs"}
    runner.set_baseline(**first_week)

    # Second week to check
    report = runner.run(**first_week)  # replace with actual second week data
    print(report.to_dict())


# ------------------------------------------------------------
# 7. INTEGRATION: with LangFuse
# ------------------------------------------------------------
def example_langfuse():
    import os
    from drift_detector.adapters.langfuse_adapter import LangFuseAdapter

    adapter = LangFuseAdapter(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    data = adapter.fetch_traces(limit=200, hours_back=168)
    print(f"Fetched {data['total_traces']} traces from LangFuse")
