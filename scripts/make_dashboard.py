import json
from pathlib import Path

queries = [
    (
        "Run latency p50 / p95",
        [
            "histogram_quantile(0.50, sum(rate(labelguard_run_seconds_bucket[5m])) by (le))",
            "histogram_quantile(0.95, sum(rate(labelguard_run_seconds_bucket[5m])) by (le))",
        ],
        "s",
    ),
    ("Completed throughput by agent", ["sum(rate(labelguard_runs_total[5m])) by (agent)"], "ops"),
    ("Worker error rate", ["sum(rate(labelguard_errors_total[5m])) by (service)"], "ops"),
    ("Service availability", ["up"], "percentunit"),
    (
        "Per-agent step latency p95",
        ["histogram_quantile(0.95, sum(rate(labelguard_step_seconds_bucket[5m])) by (le,agent,step))"],
        "s",
    ),
    ("Provider retries", ["sum(rate(labelguard_provider_retries_total[5m])) by (agent)"], "ops"),
    (
        "Per-process memory (one application process per container)",
        ["process_resident_memory_bytes"],
        "bytes",
    ),
    ("Per-process CPU seconds/second", ["rate(process_cpu_seconds_total[5m])"], "percentunit"),
    ("Tool calls per agent", ["sum(rate(labelguard_tool_calls_total[5m])) by (agent,tool)"], "ops"),
    ("Provider circuit breaker", ["labelguard_provider_circuit_open"], "short"),
    ("Cache hits / misses", ["sum(rate(labelguard_cache_total[5m])) by (outcome)"], "ops"),
    ("Provider cost by agent", ["sum(increase(labelguard_cost_total[1h])) by (agent)"], "currencyUSD"),
    ("Container process uptime", ["labelguard_uptime_seconds"], "s"),
    ("Corpus age", ["time() - labelguard_corpus_built_timestamp_seconds"], "s"),
    (
        "Corpus chunks and build throughput",
        ["labelguard_corpus_chunks", "labelguard_corpus_chunks_per_second"],
        "short",
    ),
    ("Token usage", ["sum(rate(labelguard_tokens_total[5m])) by (agent,type)"], "ops"),
]
panels = []
for i, (title, expressions, unit) in enumerate(queries):
    panels.append(
        {
            "id": i + 1,
            "type": "timeseries",
            "title": title,
            "datasource": {"type": "prometheus", "uid": "labelguard-prometheus"},
            "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8},
            "targets": [
                {
                    "expr": expression,
                    "refId": chr(65 + j),
                    "legendFormat": "{{job}} {{instance}} {{agent}} {{step}} {{outcome}}",
                }
                for j, expression in enumerate(expressions)
            ],
            "fieldConfig": {"defaults": {"unit": unit}},
            "options": {"legend": {"displayMode": "list"}},
        }
    )
dashboard = {
    "uid": "pirate-hunter-labelguard",
    "title": "Pirate Hunter | LabelGuard Operations",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "time": {"from": "now-30m", "to": "now"},
    "panels": panels,
    "tags": ["agentops", "labelguard"],
}
target = Path("infra/grafana/dashboards/labelguard.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
print("Published", len(panels), "Grafana panels")
