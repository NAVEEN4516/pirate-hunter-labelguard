# Pirate Hunter | LabelGuard

**Packaged Food Label Compliance Check Service**

ML System Design & AgentOps - UE24AM342AA5 - Mini Project 10

PES University, Department of CSE (AI & ML)

| Team member | SRN |
|---|---|
| **Naveen Prasad M** | **PES1UG24AM379** |
| Nishanth Nag | PES1UG24AM381 |
| Sateesh | PES1UG24AM397 |

A working asynchronous service for checking proposed **domestic retail processed
breakfast cereal** labels. Research and verification are separate LangGraph
agents in separate worker containers. Findings cite exact passages from bundled
official FSSAI documents. Unsupported categories, uncertain exemptions and
incomplete evidence route to a human.

**The service never authorises printing.** The assignment's `clear-for-print`
route means only “supported checks passed”; every response contains
`print_authorized:false` and requires a regulatory affairs professional's decision.

## Run from a clean checkout

Prerequisites: Docker Desktop/Engine running with Linux containers and Docker
Compose v2 supporting optional `env_file` entries (2.24+). Allow roughly 4 GB free
memory and a few GB disk for images. Internet is needed for the first image and
Python dependency downloads. The regulatory PDFs are already bundled.

```sh
docker compose up --build -d
docker compose ps
```

No API key, `.env` file, host-side Python process or downloaded model is required.
The init container builds the local index, then both workers and the API start.
The first build can take several minutes. All seven long-running services should
be healthy; `init` should have exited successfully.

| Interface | Local address |
|---|---|
| Web client | [Open LabelGuard](http://localhost:8000) |
| Interactive REST contract | [Swagger UI](http://localhost:8000/docs) |
| Worker readiness | [Readiness status](http://localhost:8000/ready) |
| Grafana operations dashboard | [Operations dashboard](http://localhost:3000/d/pirate-hunter-labelguard) |
| Jaeger connected traces | [Trace explorer](http://localhost:16686) |
| Prometheus | [Metrics explorer](http://localhost:9090) |

Default mode is an explicitly labelled **deterministic provider stub**, with a
350 ms delay per planning call. It exercises real HTTP calls, graph/tool
selection, the durable queue, two worker processes, verification, telemetry and
the UI. It is a reproducible demonstration and load-test profile, not an
evaluation of a real language model. An external provider adapter is implemented
but no external account was configured or charged during development.

Choose a demonstration in the web client, inspect/edit the full JSON if needed,
and click **Check label**. The browser submits, polls, and displays findings,
citations and the escalation path. Run activity, evidence library and the team
page are included. The workbench's quick nutrition fields use per-100g units;
use the REST contract for other valid bases.

## Reproduce the difficult protein case

```sh
curl -X POST http://localhost:8000/v1/runs -H "Content-Type: application/json" --data-binary @examples/valid-protein.json
```

Copy the returned run_id and poll:

```sh
curl http://localhost:8000/v1/runs/RUN_ID
curl http://localhost:8000/v1/runs/RUN_ID/trace
```

On Windows PowerShell use `curl.exe` instead of the `curl` alias, or use /docs.

The illustrative example supplies a reviewer-confirmed **54 g/day benchmark**;
it is an arithmetic demonstration, not proof that the benchmark is appropriate
for an actual product/population. Source-of-protein conditions for solids in the
pinned claims regulation are alternatives: 10% RDA per 100 g, 5% RDA per 100 kcal,
or 10% RDA per serving. With that benchmark they are **5.4 g/100g OR
2.7 g/100kcal OR 5.4 g/serving**. At 6 g/100g the example meets one condition;
at 3 g/100g, 376 kcal/100g and 40 g/serve it meets none. Without an applicable
reviewer-confirmed RDA basis, the service escalates.

The finding cites LD 5(3)(b), AC 5(3), AC Schedule I item 11 and AC 2(1)(n).
An independent verifier resolves the passages against the pinned corpus and
recomputes the arithmetic. Text in proposed labels is never accepted as agent
instructions. See [the reference case and viva guide](docs/DEMO.md).

## Run tests and batch evaluation inside containers

```sh
docker compose exec -T api pytest -q
docker compose exec -T api python -m labelguard.cli evaluate --output /app/output/evaluation/results.json
docker compose cp api:/app/output/evaluation/results.json output/evaluation/reproduced.json
```

The repository includes the measured fixed-set results in
`output/evaluation/results.json`. The seeded set contains **32 cases**, including
five boundary/guardrail rejects. Both prompt variants run against the same set.
The v1 baseline limits retrieval to labelling; v2 follows claim dependencies
across regulations and verifies the result. Metrics and their limits are in
[the report](docs/REPORT.md). A zero hallucination metric here is an evidence
provenance check, not proof of legal correctness.

The measured development tests cover input rejects with no job creation,
normalisation and cross-fields, prompt injection, bounded tools, independent
citation repair, tampered passage rejection, lease recovery/stale-owner
protection, provider retry/circuit behavior and safe deadlines. Screenshots and
real service traces are under `output/verification/`.

## Scaling and complete-run load tests

The SLO was declared **before** measuring: **p95 <= 15 s from submission to final
verified result**, in the local stub profile. The hard execution budget is 45 s.
Read [SLO.md](docs/SLO.md) and the report before interpreting the results.

```sh
docker compose up -d --scale agent-worker=3
```

To reproduce a containerised Locust run (cache disabled, elevated test-only rate
limit), create `output/load/current`, then:

```sh
docker compose -f compose.yaml -f compose.load.yaml up -d --scale agent-worker=3
docker compose -f compose.yaml -f compose.load.yaml --profile load run --rm loadtest
```

Override LOAD_USERS and LOAD_DURATION through your shell or a local `.env` file.
The `RUN / submission_to_result` CSV row is the assessed transaction; ordinary
POST/GET rows are only HTTP timings. `scripts/load_sweep.py` automates a six-point
sweep from the optional host dev environment. It saves every raw Locust CSV and
the measured summary in `output/load/results.json`. The paired cache experiment
is `scripts/cache_measure.py` and `output/load/cache/results.json`.

Restore normal limits/configuration afterwards:

```sh
docker compose up -d --scale agent-worker=1
```

## Corpus and configuration

Bundled official reference documents:

- Labelling and Display Regulations 2020, **version VIII, 9 Sep 2025**.
- Advertising and Claims Regulations 2018, **version IV, 14 Dec 2022**.
- Labelling and Display First Amendment 2026, notified **24 Mar 2026**, whose
  commencement provision states **1 Jul 2027**. The service escalates dates
  outside its confirmed applicability window.

Every source has a URL/version/SHA256 manifest. The compendia are reference
compilations; original Gazette notifications prevail if there is an error or
conflict. There is no claim that this small corpus is exhaustive for all label
law. Exemptions and unresolved external requirements go to a professional.

```sh
docker compose run --rm init python -m labelguard.cli index --force
```

This reuses unchanged embedding vectors. The embedding is documented local
lexical hashing through LangChain/FAISS, not a learned semantic model.
Freshness, chunk count and build throughput appear in the corpus API and metrics.

`.env.example` documents runtime settings. For a real provider, copy it to `.env`
and set LG_PROVIDER_MODE=openai_compatible, LG_PROVIDER_URL (provider-specific
base including /v1 if required), LG_PROVIDER_MODEL and LG_PROVIDER_API_KEY. Enter
the provider's actual prompt/completion prices and set an account spending
limit. Do not commit `.env`. Restart the app services after changing settings.
External model JSON/tool-plan behavior needs validation on the target provider;
the checked-in evaluation does not claim that has happened.

## Development (optional; not required for the container demo)

Python 3.12 is recommended for the pinned lock file. On Windows:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m labelguard.cli index
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m labelguard.cli evaluate
.venv\Scripts\python scripts/verify_service.py
```

Linux/macOS use `.venv/bin/python`. Dev scripts communicate with the running
container service; the application runtime remains inside containers. Browser
acceptance uses Playwright with an installed Chromium browser; the helper accepts
LG_BROWSER_CHANNEL=msedge if Edge is installed. PLAYWRIGHT_MODULE can select an
existing local Playwright package without hardcoded machine paths.

## Submission and operations material

- [Detailed demo session instructions for 29 October](docs/DEMO_SESSION.md)
- [Repository organisation](docs/REPOSITORY_GUIDE.md)
- [PowerPoint project report](output/presentation/Pirate_Hunter_Project_Report.pptx)
- [Final report](docs/REPORT.md)
- [Rendered final report PDF](output/pdf/Pirate_Hunter_Final_Report.pdf)
- [Architecture and design decisions](docs/ARCHITECTURE.md)
- [External interface contracts](docs/CONTRACTS.md) and [OpenAPI JSON](docs/contracts/openapi.json)
- [Requirement coverage and limitations](docs/REQUIREMENTS.md)
- [Runbook](docs/RUNBOOK.md) and [genuine incident log](docs/INCIDENTS.md)
- [Ten-item demonstration and viva guide](docs/DEMO.md)
- [Fixed evaluation set](eval/scenarios.json)
- [Measured outputs](output/)

Source repository: [NAVEEN4516/pirate-hunter-labelguard](https://github.com/NAVEEN4516/pirate-hunter-labelguard).
The initial delivery groups commits by implementation, test evidence and
documentation. Faculty sign-off, historical teammate contributions and a live
external-provider experiment are not claimed. Agree presentation roles before
the session. Run `scripts/demo_rehearsal.ps1` from PowerShell for six live checks.
