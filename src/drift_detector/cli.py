"""CLI: command-line interface for Canary — agent drift detection."""

import json
import time
import click
from pathlib import Path

from drift_detector.core.runner import DriftRunner
from drift_detector.adapters.jsonl_adapter import JSONLAdapter


@click.group()
def main():
    """🐤 Canary — detect reasoning drift in AI agents before they go silent."""


@main.command()
@click.option("--baseline-file", required=True, help="Path to baseline JSONL traces (known-good period)")
@click.option("--save-to", default=".canary_baseline.pkl", help="Where to save the baseline")
def baseline(baseline_file, save_to):
    """Capture a baseline from a known-good period."""
    adapter = JSONLAdapter(baseline_file)
    data = adapter.load()

    runner = DriftRunner()
    runner.set_baseline(
        reasoning_texts=data["reasoning_texts"],
        tool_counts=data["tool_counts"],
        decision_paths=data["decision_paths"],
    )

    # Save baseline to disk for later use
    import pickle
    baseline_data = {
        "embedding_baseline": runner.embedding.baseline_embeddings.tolist() if runner.embedding.baseline_embeddings is not None else None,
        "tool_usage_baseline": runner.tool_usage.baseline_dist,
        "decision_path_baseline": {"|||".join(k): v for k, v in runner.decision_path.baseline_paths.items()} if runner.decision_path.baseline_paths else None,
        "total_traces": data["total_traces"],
        "total_runs": data["total_runs"],
    }
    with open(save_to, "wb") as f:
        pickle.dump(baseline_data, f)

    click.echo(f"✅ Baseline captured from {data['total_traces']} traces ({data['total_runs']} runs)")
    click.echo(f"   Saved to {save_to}")


@main.command()
@click.option("--trace-file", required=True, help="Path to current JSONL traces to check")
@click.option("--baseline-file", default=".canary_baseline.pkl", help="Path to saved baseline")
@click.option("--output", default="-", help="Output file for report (default: stdout)")
@click.option("--threshold-embedding", default=0.15, type=float)
@click.option("--threshold-tool-usage", default=0.3, type=float)
@click.option("--threshold-decision-path", default=0.25, type=float)
def check(trace_file, baseline_file, output, threshold_embedding, threshold_tool_usage, threshold_decision_path):
    """Check current traces for drift against a baseline."""
    import pickle
    import numpy as np

    # Load baseline
    with open(baseline_file, "rb") as f:
        saved = pickle.load(f)

    # Load current traces
    adapter = JSONLAdapter(trace_file)
    data = adapter.load()

    # Restore runner with baseline
    runner = DriftRunner(
        embedding_threshold=threshold_embedding,
        tool_usage_threshold=threshold_tool_usage,
        decision_path_threshold=threshold_decision_path,
    )

    if saved.get("embedding_baseline"):
        runner.embedding.baseline_embeddings = np.array(saved["embedding_baseline"])
    if saved.get("tool_usage_baseline"):
        runner.tool_usage.baseline_dist = saved["tool_usage_baseline"]
    if saved.get("decision_path_baseline"):
        from collections import Counter
        baseline_paths = Counter()
        for path_key, count in saved["decision_path_baseline"].items():
            if isinstance(path_key, str):
                baseline_paths[tuple(path_key.split("|||"))] = count
            else:
                # Already a tuple (pickled directly from Counter)
                baseline_paths[path_key] = count
        runner.decision_path.baseline_paths = baseline_paths

    # Run detection
    try:
        report = runner.run(
            reasoning_texts=data["reasoning_texts"],
            tool_counts=data["tool_counts"],
            decision_paths=data["decision_paths"],
        )
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        click.echo("   Run 'baseline' command first to capture a baseline.", err=True)
        return

    result = report.to_dict()
    result["traces_checked"] = data["total_traces"]
    result["runs_checked"] = data["total_runs"]

    output_text = json.dumps(result, indent=2)
    if output == "-":
        click.echo(output_text)
    else:
        with open(output, "w") as f:
            f.write(output_text)
        click.echo(f"Report saved to {output}")

    if report.any_drifted():
        click.echo("\n⚠️  DRIFT DETECTED!", err=True)
    else:
        click.echo("\n✅ No drift detected.")


@main.command()
@click.option("--port", default=9090, help="Port for Prometheus metrics endpoint")
def serve(port):
    """Start a Prometheus metrics HTTP server for continuous monitoring."""
    from prometheus_client import start_http_server

    start_http_server(port)
    click.echo(f"🐤 Canary metrics available at http://0.0.0.0:{port}")
    click.echo(f"   Endpoint: http://0.0.0.0:{port}/metrics")
    click.echo("   Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n👋 Stopped.")


if __name__ == "__main__":
    main()
