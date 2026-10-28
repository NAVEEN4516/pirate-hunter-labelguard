# Ten-item live demonstration and viva guide

Team: Pirate Hunter. Naveen Prasad M (PES1UG24AM379), Nishanth Nag
(PES1UG24AM381), Sateesh (PES1UG24AM397). This records membership, not a fabricated
history of individual contributions. Suggested rehearsal ownership: Naveen -
end-to-end flow and scope; Nishanth - retrieval and evaluation; Sateesh -
deployment, reliability and load results. Agree actual roles within the team.

## Rehearsal order

1. **Clean startup:** `docker compose up --build -d`; show `docker compose ps`,
   `/ready`, and the client. Use the default stub profile; it requires no key.
2. **Valid request:** load the qualifying protein example, submit, inspect the
   recommendation. Open its protein finding and both regulatory documents.
   Point out `print_authorized:false` and the professional's final decision.
3. **End-to-end audit:** Inspect run trace in the client, or GET
   `/v1/runs/{id}/trace`. Show request-field lookup, chosen corpus query, clause
   lookup, passage text/hash, prompt version/digest, timings, synthetic stub
   usage/cost, verification outcome and the connected Jaeger trace.
4. **Malformed ingestion:** POST `examples/malformed.json`. Show 422,
   quarantine ID, field error and agent_started:false. Tests verify the jobs and
   runs tables stay empty for a rejected record; the live smoke test confirms
   run counts do not change.
5. **Cannot answer:** use the outside-category or small-pack example. Show
   regulatory-review and the concrete human action; no invented approval.
6. **Self-verification:** in a local rehearsal enable LG_ENABLE_FAULTS=true on
   API/workers, then run `scripts/fault_demo.py` from the dev environment. It
   submits an unsupported candidate via the documented demo header. The first
   verification event fails, a repair occurs, and the new candidate passes.
   Actual traces are saved under `output/verification/fault-results.json`.
7. **Injection:** use the prompt-injection example. The API rejects/quarantines
   it before a model or tool executes. Nested strings are also covered by tests.
8. **Circuit breaker:** the fault script makes the stub unavailable. Show three
   failed attempts, exponential backoff, circuit open and a subsequent fast
   escalation. Reset the provider and disable demo controls afterwards.
9. **Load/scaling:** show the SLO declared before measuring, the complete-run
   Locust CSV rows and the 1-worker/3-worker results. Compare p95 and RPS at the
   same concurrency; identify the first *tested* concurrency that misses the
   target. Do not call 202 response time complete-run latency.
10. **Protein difficult case:** with the demo's supplied 54 g/day benchmark,
    source thresholds for a solid food are 5.4 g/100g OR 2.7 g/100kcal OR
    5.4 g/serving. At 6 g/100g, 376 kcal/100g and 40 g/serve the first branch
    passes. At 3 g/100g all three fail. Also demonstrate 4 g/100g at 120 kcal
    (energy branch passes), and 4 g/100g at 150 g/serve (serving branch passes).
    The newer version-IV Schedule I includes that serving alternative.

## Reference evidence for Evaluation 1

- LD-5.3: Labelling and Display 2020, version VIII, regulation 5(3)(b), pp 10–11.
- AC-5.3: Advertising and Claims 2018, version IV, regulation 5(3), p 4.
- AC-PROTEIN: the same claims regulation, Schedule I item 11, p 9.
- AC-RDA: the same claims regulation, 2(1)(n), p 2 (current ICMR RDA basis).
- The 2026 labelling amendment is bundled as a future applicability document;
  its regulation 1(2), p 5, starts it on 1 July 2027. Dates at/after that point
  escalate in this version.

These are reproducible corpus passages and candidate test values. Faculty
confirmation at Evaluation 1 and expert confirmation of the actual product's
RDA benchmark remain human activities; do not claim they already happened.

## Viva questions to rehearse

- Why two agents? Separate retrieval planning and independent policy/citation
  verification, distinct graphs and processes, durable hand-off and failure isolation.
- What makes retrieval agentic? The planner chooses tools based on fields,
  previously read provisions and unmet dependencies. Verification can select a
  different retrieval strategy or escalate.
- Why not a single vector search? The question names the nutrition panel; the
  claim threshold lives in a different regulation. Exact dependency following
  addresses that structural gap.
- Why lexical hashing? Tiny corpus, no downloads/cost, reproducible local
  baseline. It is not semantic retrieval; limitations are explicit and the
  clause-link strategy does the difficult cross-regulation work.
- What if a worker dies? Lease expiry permits reclaim; ownership checks reject
  stale writes, attempts are bounded, and old runs may safely escalate.
- Is clear-for-print an approval? No. It is the required route enum for supported
  checks; the response cannot authorise printing. The UI makes this explicit.
- Are zero hallucinations proof of legal accuracy? No. These deterministic
  metrics verify evidence provenance and rule consistency on a fixed set; they
  do not replace independent expert judgement or an unseen-case evaluation.
- What was actually measured? Local stub-mode correctness, real HTTP/worker
  integration, failure exercises, browser acceptance and complete-run load tests.
  External provider quality/cost is not represented as measured.
