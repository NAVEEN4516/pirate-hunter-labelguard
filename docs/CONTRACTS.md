# Published interface contracts

All interfaces use UTF-8 JSON except HTML/static assets and Prometheus text.
Unknown request fields are forbidden. Numeric NaN/Infinity, out-of-range values,
unknown categories, impossible chronology and inconsistent nutrient/serving
relationships are rejected before a job is inserted. Data units are part of the
field name. `contract_version` is `1.0`. Missing declarations are valid business
data that yield an unmet finding; malformed declarations are ingestion rejects.

| Interface | Success contract | Rejections / semantics |
|---|---|---|
| POST /v1/runs | 202 `{run_id,status,status_url,cached,correlation_id}` | 422 field errors + quarantine_id + agent_started:false; 413 >64 KiB; 429 with Retry-After |
| GET /v1/runs/{id} | 200 `{run_id,status,submitted_at,updated_at,latency_s,cached,correlation_id,result,usage}` | 404 unknown; result null while pending or failed |
| GET /v1/runs/{id}/trace | 200 `{run_id,correlation_id,events:[{id,run_id,timestamp,agent,kind,data}]}` | 404 unknown; data payload depends on documented event kind |
| POST /v1/runs/{id}/feedback | 201 `{saved:true}`; body feedback.schema.json | 404 unknown, 409 not complete, 422 invalid/toxic reason, 429 rate limit |
| GET /v1/quarantine/{id} | `{id,created,errors,correlation_id,agent_started:false}` | 404 unknown; raw rejected content not returned |
| GET /v1/passages/{id} | Source metadata + exact text, topics and links | 404 unknown; read-only public corpus |
| GET /v1/corpus | Index manifest, source versions/hashes, build time and throughput | Requires startup index; no automatic online legal update |
| GET /v1/dashboard | Recent runs, aggregate counts, worker heartbeats, agent metrics, feedback, sampled quality | Local read-only operations data |
| GET /v1/contract | request JSON schema | Live equivalent of request.schema.json |
| GET /v1/info | `{mode,prompt_version,print_authorized:false}` | No credentials or provider endpoint exposed |
| GET /v1/examples/{name} | One of six allowlisted request examples | 404 unknown; no arbitrary filesystem lookup |
| GET /health | `{status,service,version}` | Liveness only |
| GET /ready | `{ready,active_worker_stages,corpus_version}` | 503 if either worker stage lacks a fresh heartbeat |
| GET /metrics | Prometheus exposition text | Read-only monitoring interface |

The result schema is `recommendation.schema.json`. Routes are clear-for-print,
revise-and-recheck and regulatory-review. Findings are met, unmet,
insufficient_evidence or not_applicable. Citations include passage ID, document,
clause, page, source URL, exact quote and source SHA256. `verified:true` means the
returned findings or escalation passed the deterministic policy/citation checks;
it does not mean an entire label has legal approval. `print_authorized` can only
be false. The UI renames clear-for-print to “Supported checks passed”.

Queue/state transitions:
`queued -> research -> verification-queued -> verification -> completed`.
Normal failures yield completed regulatory-review with a service-reliability
finding. A worker killed repeatedly may end in failed; no confident answer is
returned. Jobs are at-least-once; final writes are lease-owner conditional.

Polling is chosen over callbacks because it needs no exposed caller endpoint,
callback credentials or retry/delivery contract. Poll 2–5 times per second during
a run; the provided client uses 400 ms. A durable run can be polled after refresh.

Internal provider-stub POST /plan accepts `{context,prompt_version}` and returns
`{plan:{tool,arguments,reason},usage:{prompt_tokens,completion_tokens},usage_kind}`.
Plan is strictly validated; tools and their argument schemas are allowlisted.
Stub token counts are explicit character/4 estimates for reproducibility, not
real model tokenisation. Fault controls are disabled unless LG_ENABLE_FAULTS=true.
An external provider uses its OpenAI-compatible chat-completions interface;
the base address, model, key and prices are supplied at runtime.

Trace events: submitted, model, tool, step, provider_failure, provider_circuit,
tool_error, verification, publish, task_completed, worker_error and job_exhausted.
Model events record prompt digest/context/plan, reported usage, price at call time,
retries, latency and cost. Tool events record arguments and complete retrieved
passages. Failures without usage do not invent token counts. Unknown usage on
a failed provider attempt is a cost-accounting limitation.
