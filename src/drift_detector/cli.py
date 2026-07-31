"""CLI: command-line interface for Canary — agent drift detection."""

import json
import time
import click
from pathlib import Path

from drift_detector.core.runner import DriftRunner
from drift_detector.adapters.jsonl_adapter import JSONLAdapter


def _load_data(source, file_path, trace_name, hours_back):
    """Load traces from the configured source. Returns normalized dict."""
    if source == "langfuse":
        from drift_detector.adapters.langfuse_adapter import LangFuseAdapter

        adapter = LangFuseAdapter(
            trace_name=trace_name,
            hours_back=hours_back,
        )
        return adapter.fetch_traces()
    else:
        # Default: JSONL file
        if not file_path:
            raise click.UsageError("--trace-file is required for source=jsonl")
        adapter = JSONLAdapter(file_path)
        return adapter.load()


@click.group()
def main():
    """🐤 Canary — detect reasoning drift in AI agents before they go silent."""


@main.command()
@click.option("--source", default="jsonl", type=click.Choice(["jsonl", "langfuse"]),
              help="Trace source: jsonl file or LangFuse")
@click.option("--baseline-file", default=None, help="Path to baseline JSONL traces (known-good period)")
@click.option("--trace-name", default="", help="Filter by trace name (LangFuse only)")
@click.option("--hours-back", default=168, type=int, help="Hours back to fetch (LangFuse only)")
@click.option("--save-to", default=".canary_baseline.pkl", help="Where to save the baseline")
def baseline(source, baseline_file, trace_name, hours_back, save_to):
    """Capture a baseline from a known-good period."""
    if source == "jsonl" and not baseline_file:
        raise click.UsageError("--baseline-file is required for source=jsonl")

    data = _load_data(source, baseline_file, trace_name, hours_back)
    if not data["reasoning_texts"]:
        click.echo("❌ No traces found. Check your source configuration.", err=True)
        return

    runner = DriftRunner()
    runner.set_baseline(
        reasoning_texts=data["reasoning_texts"],
        tool_counts=data["tool_counts"],
        decision_paths=data["decision_paths"],
    )

    import pickle

    baseline_data = {
        "embedding_baseline": runner.embedding.baseline_embeddings.tolist() if runner.embedding.baseline_embeddings is not None else None,
        "tool_usage_baseline": runner.tool_usage.baseline_dist,
        "decision_path_baseline": {"|||".join(k): v for k, v in runner.decision_path.baseline_paths.items()} if runner.decision_path.baseline_paths else None,
        "total_traces": data.get("total_traces", 0),
        "total_runs": data.get("total_runs", 0),
        "source": source,
    }
    with open(save_to, "wb") as f:
        pickle.dump(baseline_data, f)

    click.echo(f"✅ Baseline captured from {data.get('total_traces', '?')} traces ({data.get('total_runs', '?')} runs)")
    click.echo(f"   Source: {source}")
    click.echo(f"   Saved to {save_to}")


@main.command()
@click.option("--source", default="jsonl", type=click.Choice(["jsonl", "langfuse"]),
              help="Trace source: jsonl file or LangFuse")
@click.option("--trace-file", default=None, help="Path to current JSONL traces to check")
@click.option("--trace-name", default="", help="Filter by trace name (LangFuse only)")
@click.option("--hours-back", default=168, type=int, help="Hours back to fetch (LangFuse only)")
@click.option("--baseline-file", default=".canary_baseline.pkl", help="Path to saved baseline")
@click.option("--output", default="-", help="Output file for report (default: stdout)")
@click.option("--threshold-embedding", default=0.15, type=float)
@click.option("--threshold-tool-usage", default=0.3, type=float)
@click.option("--threshold-decision-path", default=0.25, type=float)
def check(source, trace_file, trace_name, hours_back, baseline_file, output,
          threshold_embedding, threshold_tool_usage, threshold_decision_path):
    """Check current traces for drift against a baseline."""
    import pickle
    import numpy as np

    # Load baseline
    with open(baseline_file, "rb") as f:
        saved = pickle.load(f)

    # Load current traces
    data = _load_data(source, trace_file, trace_name, hours_back)
    if not data["reasoning_texts"]:
        click.echo("❌ No traces found. Check your source configuration.", err=True)
        return

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
    result["traces_checked"] = data.get("total_traces", 0)
    result["runs_checked"] = data.get("total_runs", 0)

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