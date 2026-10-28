# Repository guide

Start with [README](../README.md) for installation and the demo. The repository
separates implementation, reproducible inputs, operational configuration and
measured evidence.

| Folder or file | Purpose |
|---|---|
| `labelguard/` | FastAPI service, two LangGraph agents, queue, retrieval, policy and telemetry |
| `web/` | Browser workbench, results, evidence library and team page |
| `data/raw/` | Official source PDFs with manifest and hash pinning in `data/sources.json` |
| `prompts/` | Research v1/v2 and verifier prompt versions |
| `examples/` | Demonstration requests including invalid and out-of-scope inputs |
| `tests/` | Boundary, policy, lease and provider tests |
| `eval/` | 32 fixed evaluation scenarios |
| `loadtests/` | Complete-run Locust workload |
| `infra/` | Prometheus and Grafana provisioning |
| `compose.yaml` | Normal seven-service deployment and initialiser |
| `compose.load.yaml` | Explicit load-test overrides |
| `docs/` | Architecture, contracts, requirement coverage, runbook and viva guide |
| `output/evaluation/` | Saved baseline and revised prompt measurements |
| `output/load/` | Raw load-test CSVs and cache measurement |
| `output/verification/` | Test, browser, fault and monitoring evidence |
| `output/pdf/` | Final written project report |
| `output/presentation/` | Editable PowerPoint report |
| `scripts/` | Ingestion, evaluation support, verification and packaging helpers |
| `.github/workflows/ci.yml` | Linux tests, lint, evaluation and Compose validation |

The Git history groups the initial delivery by implementation, validation and
documentation. These commits organise the submission; they do not claim a
historical development timeline or individual teammate contributions.

Runtime databases, credentials, virtual environments, generated indexes and
temporary render files are ignored. The official PDFs and measured evidence stay
in the repository so reviewers can reproduce the demonstration.

## Presentation

The PowerPoint contains 17 slides with editable text and native result tables.
Each slide includes source and explanation notes. `scripts/build_presentation.mjs`
exports `buildReport(presentation, root)` for the Artifact presentation runtime.
It uses the saved viewport screenshots under `output/demo/`.
`scripts/export_presentation.mjs` recreates and validates a local PPTX using that
same content builder and the bundled Artifact Tool runtime.
