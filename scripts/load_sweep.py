"""Run real containerised Locust tests and preserve the complete-run statistics."""

import csv
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/load"
OUT.mkdir(parents=True, exist_ok=True)
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.load.yaml"]
MATRIX = [(1, 2), (1, 4), (1, 8), (3, 4), (3, 8), (3, 20)]


def command(args, env, log):
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)


def wait_ready():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if httpx.get("http://127.0.0.1:8000/ready", timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Service did not become ready")


def main():
    results = []
    for replicas, users in MATRIX:
        label = f"workers-{replicas}_users-{users}"
        case = OUT / label
        case.mkdir(exist_ok=True)
        env = {
            **os.environ,
            "LG_CACHE_ENABLED": "false",
            "LG_ENABLE_FAULTS": "false",
            "LOAD_USERS": str(users),
            "LOAD_DURATION": "30s",
        }
        print("Measuring", label, flush=True)
        command(
            COMPOSE
            + [
                "up",
                "-d",
                "--no-build",
                "--scale",
                f"agent-worker={replicas}",
                "api",
                "agent-worker",
                "verifier-worker",
                "provider-stub",
            ],
            env,
            case / "startup.log",
        )
        wait_ready()
        current = OUT / "current"
        current.mkdir(exist_ok=True)
        command(COMPOSE + ["--profile", "load", "run", "--rm", "loadtest"], env, case / "locust.log")
        for file in current.glob("locust*.csv"):
            shutil.copy2(file, case / file.name)
        stats = list(csv.DictReader((case / "locust_stats.csv").open(encoding="utf-8")))
        row = next(r for r in stats if r["Type"] == "RUN" and r["Name"] == "submission_to_result")
        result = {
            "workers": replicas,
            "concurrency": users,
            "stub_delay_s": 0.35,
            "cache_enabled": False,
            "complete_run_count": int(row["Request Count"]),
            "failed_or_escalated_runs": int(row["Failure Count"]),
            "rps": float(row["Requests/s"]),
            "p50_s": float(row["50%"]) / 1000,
            "p95_s": float(row["95%"]) / 1000,
            "mean_s": float(row["Average Response Time"]) / 1000,
            "slo_target_s": 15,
            "slo_met": float(row["95%"]) <= 15000 and int(row["Failure Count"]) == 0,
            "raw_directory": str(case.relative_to(ROOT)).replace("\\", "/"),
        }
        results.append(result)
        (OUT / "results.json").write_text(
            json.dumps(
                {
                    "measured_at": time.time(),
                    "method": "Containerised Locust complete-run transactions. Includes queueing and polling. Quantiles use Locust buckets. Closed-loop workload, 30 s arrival period, in-flight transactions allowed to drain for up to 50 s. Low sample counts limit tail estimates.",
                    "results": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(json.dumps(result), flush=True)
    # Leave an ordinary development configuration, with a single research worker.
    command(
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
        os.environ,
        OUT / "restore.log",
    )
    print("Load sweep complete; raw CSVs and measured summaries saved.", flush=True)


if __name__ == "__main__":
    main()
