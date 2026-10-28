# Requirement coverage and honest limits

“Implemented” means source, fixtures and local verification exist. It does not
mean legal certification or live-model performance. The assignment explicitly
allows prioritisation; unsupported surfaces are documented instead of presented
as finished production capabilities.

| ID | Status | Evidence / limit |
|---|---|---|
| F1 | Implemented | FastAPI POST /v1/runs; live/exported OpenAPI and JSON schemas |
| F2 | Implemented | Pydantic boundary/range/category/cross-fields; persistent quarantine; zero jobs for rejects |
| F3 | Scoped | Conservative breakfast-cereal classification plus rule/synonym claim detection; ambiguous names/special categories escalate |
| F4 | Scoped | Agent-selected LangChain/FAISS search and clause lookup; protein, sugar and fibre claim provisions |
| F5 | Scoped | Requirement findings with exact retrieved clause/page/text/hash; independent deterministic checks |
| F6 | Implemented | Three required route codes; literal-false print authority; UI advisory labels |
| F7 | Implemented within scope | Exemptions, outside categories, unknown claims, incomplete evidence and service failures escalate |
| F8 | Implemented | Health/readiness, Prometheus metrics, JSON logs, durable audit events |
| A1 | Implemented | LangGraph research planner selects three typed read-only tools; step/tool/time bounds |
| A2 | Implemented | Distinct research/verification graphs in separate OS processes/containers; atomic queue hand-off |
| A3 | Implemented | Citation/passage integrity, independent rule recomputation, bounded repair then safe review |
| A4 | Implemented | Immediate run ID, durable leased queue, polling with documented rationale |
| A5 | Implemented | Per-attempt/tool timeouts, exponential retries, per-worker breaker, no confident failure fallback; actual fault evidence |
| A6 | Implemented | Per-agent task success, steps/tools, step/end-to-end latency, retries/tokens/cost, worker/container-process uptime in UI/Grafana |
| A7 | Implemented locally | Compose scaling 1 -> 3 research workers; actual Locust measurements preserved |
| A8 | Implemented | Responsive web client submits, polls and displays citations, trace, review action and feedback |
| L1 | Implemented with limit | LangChain + FAISS, clause/page chunking, incremental embeddings. Local hashing is lexical, not learned semantic embedding |
| L2 | Implemented for fixture profile | Versioned prompts and digests; same 32-case evaluation of v1/v2. Real provider comparison unmeasured |
| L3 | Scoped equivalent evaluator | Fixed gold outcomes/passages, CLI batch; four defined deterministic metrics, before/after retrieval change. No independent semantic LLM judge or legal expert scores |
| L4 | Layered, limited detectors | Every string screened; Unicode normalisation, read-only tool allowlists, output authority checks. Pattern-based toxicity/injection is not comprehensive |
| L5 | Implemented with accounting limit | Per-call reported usage/configured prices + per-run aggregation; stub usage marked synthetic, actual cost zero. Failed calls with no returned usage have unknown billing |
| L6 | Implemented | Persisted feedback, satisfaction aggregate, deterministic live-run sample and quality-history chart |
| D1 | Implemented | Published request/result/feedback schemas, OpenAPI and interface catalog; ingestion validation/quarantine |
| D2 | Implemented | Idempotent PDF pipeline; hash/anchor validation; incremental vector cache; freshness/count/throughput exposed |
| D3 | Implemented locally | 7 long-running services + init, Compose dependencies/healthchecks, no host runtime required; clean initial named volumes used |
| D4 | Implemented | External provider config runtime only; optional .env example; no committed credentials/account/model ID. Public corpus URLs and internal deployment addresses intentionally documented |
| D5 | Implemented with resource limit | Connected cross-service OTLP trace verified in Jaeger, complete durable event reconstruction, DNS scrape for replicas, Grafana panels. Default CPU/RAM metrics cover application processes; broader container metrics require optional host-specific cAdvisor |
| D6 | Measured local profile | Predeclared 15 s p95; Locust submission -> completion, RPS and tested failure concurrency; stub delay 350 ms. Small samples/closed-loop tests limit capacity inference |
| D7 | Implemented and measured | Request/corpus/prompt/provider-keyed TTL result cache; per-peer rate limit; paired p95/call/cost measurements. Zero actual stub cost means no dollar saving can be claimed |
| D8 | Implemented | Two failure-mode runbooks; genuine registry/bootstrap and browser-runtime development incidents, distinct from injected failures |

Remaining work before using this for real regulatory operations: expert corpus
and RDA confirmation, current Gazette/amendment completeness review, actual
product/laboratory substantiation, broader ingredient/claim coverage, model
provider calibration, authentication/authorisation, retention policy, multi-host
queue/storage and longer capacity tests. These do not prevent the documented
local assignment demonstration from running.
