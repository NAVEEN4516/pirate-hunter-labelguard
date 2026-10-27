"""Paired completed-run measurements: caching disabled vs warmed result cache."""

import json
import os
import subprocess
import time
from pathlib import Path
import httpx
from verify_service import wait
from load_sweep import wait_ready

OUT = Path("output/load/cache")
OUT.mkdir(parents=True, exist_ok=True)
payload = json.loads(Path("examples/valid-protein.json").read_text())
payload["declarations"]["batch_number"] = "CACHE-PAIRED-MEASUREMENT"
output = {
    "method": "10 identical submissions per condition, sequential, real HTTP and two worker processes. Warm-cache priming request excluded. Stub mode, zero actual provider price.",
    "conditions": {},
}
for enabled in [False, True]:
    env = {**os.environ, "LG_CACHE_ENABLED": str(enabled).lower(), "LG_ENABLE_FAULTS": "false"}
    with (OUT / f"startup-{enabled}.log").open("w") as stream:
        subprocess.run(
            [
                "docker",
                "compose",
                "up",
                "-d",
                "--no-build",
                "--scale",
                "agent-worker=1",
                "api",
                "agent-worker",
                "verifier-worker",
                "provider-stub",
            ],
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
        )
    wait_ready()
    rows = []
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
        if enabled:
            accepted = client.post("/v1/runs", json=payload).raise_for_status().json()
            wait(client, accepted["run_id"])
        for number in range(10):
            started = time.monotonic()
            accepted = client.post("/v1/runs", json=payload).raise_for_status().json()
            run = wait(client, accepted["run_id"])
            assert run["result"]["route"] == "clear-for-print"
            rows.append(
                {
                    "latency_s": time.monotonic() - started,
                    "server_latency_s": run["latency_s"],
                    "cached": run["cached"],
                    "cost": run["usage"]["cost"],
                    "model_calls": run["usage"]["model_calls"],
                }
            )
    latencies = sorted(r["latency_s"] for r in rows)
    value = {
        "p50_s": (latencies[4] + latencies[5]) / 2,
        "p95_s": latencies[9],
        "mean_cost_per_run": sum(r["cost"] for r in rows) / 10,
        "cost_per_100_runs": sum(r["cost"] for r in rows) * 10,
        "mean_model_calls": sum(r["model_calls"] for r in rows) / 10,
        "rows": rows,
    }
    output["conditions"]["warm_cache" if enabled else "cache_disabled"] = value
    print("cache", enabled, "p95", value["p95_s"], "model calls", value["mean_model_calls"], flush=True)
(OUT / "results.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
