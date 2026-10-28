# Operations runbook

## Start, stop and inspect

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail=80 api agent-worker verifier-worker
```

Open the client on port 8000, interactive API on /docs, Grafana on port 3000,
Jaeger on port 16686 and Prometheus on port 9090, all on localhost. `/health` is
API liveness; `/ready` checks both worker stages and the index. A healthy API
alone does not establish a usable system.

```sh
docker compose stop
docker compose up -d
```

Named volumes retain the index, runs, quarantine, feedback and audit events.
Back up the state volume while services are stopped. Deleting the `state` volume
destroys those records; it is not a normal recovery step.

## Failure mode 1: provider unavailable, timeout or malformed plan

**Symptom:** recommendations route to regulatory-review, provider_failure /
provider_circuit events occur, retry/circuit panels increase. A clear finding
must never be substituted for an incomplete run.

**Confirm:** inspect `/v1/runs/{id}/trace`, then research and stub logs. Check the
configured mode and the provider's health. An external provider requires its
runtime URL, model, key and prices. Do not paste keys into logs or screenshots.
Failures after 3 attempts open a per-worker circuit for 20 s; later calls fail
fast. A new process starts with a closed circuit.

**Recover:** restore the provider/network/configuration; if demo fault mode was
enabled, POST `/fault/normal` to the local stub. Wait for cooldown or restart
the research worker after the provider is healthy. Submit a new request.
Service-failure escalations are excluded from result caching. Keep the failed
run for evidence instead of rewriting its history.

## Failure mode 2: queue grows or a worker dies mid-run

**Symptom:** run status remains queued/research/verification, `/ready` may fail,
heartbeat age increases, complete-run p95 rises. A healthy submission endpoint
can still hide a failed consumer.

**Confirm:** `docker compose ps`; inspect worker logs and dashboard heartbeats.
Look up the durable event trace by run ID. If provider waiting dominates, the
research queue grows while verification stays short. If SQLite contention is the
cause, logs show lock/busy errors and adding workers stops improving throughput.

**Recover:** restart the failed worker. Its unfinished job becomes reclaimable
after the 90 s lease; attempts are limited to two. Submission wall-clock budgets
still apply, so a reclaimed old request can safely escalate. An owner that lost
its lease cannot publish. Fix the cause, then submit a fresh label if needed.

Scale the research stage within the measured single-host range:

```sh
docker compose up -d --scale agent-worker=3
```

Scale verification separately only if its queue is the measured bottleneck.
Default research and verifier limits are independent. Do not change the SLO
after seeing a poor measurement.

## Bootstrap registry/network failure

If Docker says `http: server gave HTTP response to HTTPS client` while pulling,
first confirm the Docker engine is running (`docker info`). Retry a known base
image pull and the Compose start. During this development session the error was
transient and a retry succeeded; no global proxy/TLS settings were changed.
If persistent, diagnose the actual proxy/registry configuration rather than
disabling TLS or deleting existing unrelated images.

## Reindexing and source changes

```sh
docker compose run --rm init python -m labelguard.cli index --force
```

This reuses unchanged embedding vectors. A SHA mismatch or unresolved clause
anchor must be reviewed against the source PDF; do not bypass the check. To
intentionally refresh corpus documents, use `scripts/fetch_corpus.py`, review
`data/sources.json` and `data/clause_map.json`, rebuild the image and reindex.
Restart API/workers to load a changed index. The API does not silently refresh
law while a run is executing.

## Demonstration controls and load tests

`LG_ENABLE_FAULTS=true` enables local stub `/fault/{normal|unavailable|timeout|malformed}`
and submission header `X-Demo-Fault: unsupported`. Disable after demonstration.
These are not public administration APIs. `scripts/fault_demo.py` persists actual
rejection/repair and breaker evidence; the provider is restored in a finally block.

Load testing is isolated through `compose.load.yaml`. It disables caching and
raises the direct-client rate limit. Do not use that override in ordinary runs.
The app defaults to 30 writes/minute/client. Never use a real paid provider for
the seeded load sweep. See `docs/SLO.md` before measuring.

## Monitoring and retention limitations

Jaeger all-in-one uses in-memory trace storage; a restart clears Jaeger views.
SQLite audit events remain durable. Grafana/Prometheus volumes persist metrics
and configuration. Application-process CPU/RAM are collected by default; optional
Linux cAdvisor requires the `resources` profile and host-specific mounts. Add its
scrape target only when running that profile. Raw requests may contain product
data, so establish a retention and access policy before any non-local deployment.
