# SLO declaration (before load measurements)

Declared 27 October 2026, before running any load test:

- For valid, in-scope uncached requests in the declared local stub profile, 95% of
  submissions should reach a verified final result within **15 seconds**.
- Measure submission -> final polling result, including both queues and all agent
  calls. A 202 response is not completion. Record unsuccessful/time-limited runs.
- Also report verified completion throughput, p50, p95, sample count, errors,
  replica count, client concurrency and stub delay. Report safe escalations
  separately from successful, fully evidenced determinations.
- The 15 s target suits an analyst's interactive pre-print check and leaves a
  margin above the seeded provider's multiple 350 ms planning calls. There is
  no safety reason to trade verified evidence for an immediate confident answer.
- Execution is independently bounded at 45 s from submission. Queue overload
  may cause the 15 s SLO to fail before the hard budget is reached.
- Reference workload: examples/valid-protein.json, 350 ms per provider plan,
  cache disabled, isolated local Docker Desktop, one verifier, 1 then 3 research
  workers. Sweep concurrency; do not tune this target after observing results.

The checked-in results are measurements of this hardware and stub, not an SLA
for a live LLM provider or a universal capacity claim.
