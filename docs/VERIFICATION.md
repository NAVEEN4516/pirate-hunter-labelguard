# Final verification report

Story: an analyst loads a proposed cereal label in the browser, submits it through
FastAPI validation, receives a run ID, waits for two durable worker stages, and
gets a verified, cited recommendation or an explicit escalation.

| Boundary | Result | Actual evidence |
|---|---|---|
| Container startup | Pass | New initial named volumes; final seven services healthy; output/verification/final-containers.json |
| UI render and console | Pass | Desktop/mobile Playwright acceptance, zero page errors; browser-results.json and screenshots |
| Client -> API | Pass | Real browser submission receives 202 and polls to completion |
| API -> boundary controls | Pass | Malformed/injected examples return 422, quarantine IDs and unchanged run counts; tests assert no jobs are inserted |
| Queue -> research worker | Pass | Actual run traces record chosen request_fields/search/lookup calls and prompt versions |
| Research -> verification | Pass | Separate containers/processes and durable hand-off; verification events in every live example |
| Evidence -> result | Pass | Every citation quote resolves exactly to GET /v1/passages/{id}; correct protein pass/fail routes |
| Result -> UI | Pass | Expected recommendation, citations, activity, team identity and feedback controls render |
| Fault handling | Pass | Real injected tampered candidate fails verification before repair; provider outage opens breaker and escalates |
| Cross-service tracing | Pass | Saved connected Jaeger trace includes API, research, stub and verification services |
| Metrics | Pass | Final Prometheus scrape targets all up; Grafana and Jaeger return 200 |
| Automated policy/boundary tests | Pass | 21 tests inside final Linux container; final-tests.xml |
| Fixed-set evaluation | Pass | v2 32/32; v1 14/32; final-container-results.json |
| Load target | Mixed by measured concurrency | 15 s p95 met/missed as reported; no target changes or fabricated passing results |
| Real external LLM | Unmeasured | Adapter request/plan/usage accounting tested with MockTransport; no external credentials or live model quality claim |
| GitHub publication | Pushed | NAVEEN4516/pirate-hunter-labelguard; first CI run passed |
| Demo rehearsal, 28 October | Pass | scripts/demo_rehearsal.ps1 checked six live cases; output/demo/rehearsal.json |
| PowerPoint report | Pass | 17 slides, 9 native tables, embedded viewport screenshots; package/layout/import checks and visual inspection |

All output files named without a prefix above are under output/verification/
except final-container-results.json (output/evaluation/) and load CSVs
(output/load/). The nine-page report PDF was rendered and visually reviewed;
its team identities, tables, architecture diagram and page layout were checked.

Development failures and actual fixes: the first registry pull failed and a
subsequent normal retry succeeded; Playwright's expected Chromium binary was
missing and the installed Edge channel passed the browser test. See INCIDENTS.md.
The documented LangChain community deprecation warning remains a maintenance
warning in the pinned dependency version; it did not fail any test. Future
upgrades should be validated before changing the lock file.
