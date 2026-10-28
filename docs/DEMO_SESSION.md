# Demo session guide: 29 October 2026

For Pirate Hunter, Mini Project 10, ML System Design & AgentOps (UE24AM342AA5).
Naveen Prasad M (PES1UG24AM379), Nishanth Nag (PES1UG24AM381),
Sateesh (PES1UG24AM397).

## 1. What to give the evaluator

Prepare one submission folder or message containing these items. Use any
faculty-provided submission format or template in preference to this suggested
package.

| Item | Where to get it | What the evaluator uses it for |
|---|---|---|
| GitHub repository | https://github.com/NAVEEN4516/pirate-hunter-labelguard | Source, installation, tests, configuration and reproducible evidence |
| PowerPoint | `output/presentation/Pirate_Hunter_Project_Report.pptx` | 17-slide explanation, screenshots, result tables and speaker notes |
| Written report | `output/pdf/Pirate_Hunter_Final_Report.pdf` | Detailed architecture, evaluation, load testing and limits |
| Complete backup ZIP | `dist/Pirate_Hunter_LabelGuard_Submission.zip` | A portable copy if GitHub or internet access fails |
| This demo guide | `docs/DEMO_SESSION.md` | Exact startup, demonstration and recovery steps |

The ZIP is a local download and is excluded from Git to avoid duplicating the
whole project. The report and PowerPoint are in GitHub. If an evaluator cannot
access a private repository, arrange access or provide the ZIP. A repository
link alone does not grant access. The repository visibility at publication can
be checked on GitHub.

**For the live session:** bring your laptop, charger and any required display
adapter. Run the application on your own laptop and share/project that screen.
Give the evaluator the repository, PPT and report. They do not need to install
anything just to watch. `localhost:8000` works only on the computer running the
service, so it is not a remotely accessible deployment link.

**What input you provide to the service:** choose a built-in example or supply a
JSON file following `docs/contracts/request.schema.json`. It includes
product details, declarations, ingredients, nutrition values, package data,
assessment date and any claim/RDA basis. The supported demo accepts structured
text and numbers. It does not accept photographs, scanned labels or arbitrary
PDF uploads. Sample inputs and official regulatory PDFs are already bundled.
Demo mode needs no API key or external model login.

## 2. Preparation today, 28 October

1. Open Docker Desktop and wait until its Linux engine is running. Plug in the
   charger and avoid installing/upgrading dependencies immediately before the
   session.
2. Open PowerShell in the project folder and run:

   ```powershell
   Set-Location 'C:\Users\LENOVO\OneDrive - PESUNIVERSITY\subject\AGENTOPS\PROJECT'
   docker info
   docker compose up --build -d
   docker compose ps -a
   curl.exe -fsS http://localhost:8000/ready
   ```

   On another laptop, clone the repository first, then `cd pirate-hunter-labelguard`.
   The first build needs internet for container images/dependencies and may take
   several minutes. Build now so the session can reuse local images.
3. Confirm seven services are running and healthy: `api`, `agent-worker`,
   `verifier-worker`, `provider-stub`, `prometheus`, `grafana`, `jaeger`.
   `init` should show `Exited (0)` after initialisation. Check readiness as well
   as container status. Readiness should report both worker stages available.
4. Run the prepared six-case rehearsal:

   ```powershell
   & .\scripts\demo_rehearsal.ps1
   ```

   It runs real API requests for pass, revision, two review cases and two
   quarantine cases. It uses unique batches to exercise the agents rather than
   only returning cached answers. Expect the final message `All six demo cases
   passed`. It writes `output/demo/rehearsal.json` and four actual run traces.
   If your institution's PowerShell policy prevents scripts, use the UI or the
   individual commands below. There is no need to weaken the system policy.
5. Open the PowerPoint locally, check that the screenshots appear, and rehearse
   the hand-offs between teammates. Keep the PDF and ZIP downloaded locally.
6. Check the six UI example names in the next section. Rehearse the main story
   within 10–12 minutes. Do not run a full load sweep during the opening demo.

## 3. Open these tabs before presenting

| Tab | URL or file | Purpose |
|---|---|---|
| Application | http://localhost:8000 | Main live demonstration |
| Swagger | http://localhost:8000/docs | Prove asynchronous submission and inspect JSON |
| Readiness | http://localhost:8000/ready | Show consumers and index are ready |
| Grafana | http://localhost:3000/d/pirate-hunter-labelguard | Agent work, retries, latency, token/cost accounting |
| Jaeger | http://localhost:16686 | Cross-service trace |
| GitHub | Repository link above | Folder structure, tests and reports |
| PowerPoint | Local PPTX | Scope, architecture and measured results |

Prometheus is available at http://localhost:9090 if asked. Default Grafana access
is configured for local demo viewing. Use the web app's **Run activity** for
operational evidence if a monitoring tab is slow.

On the day, start 20–30 minutes early:

```powershell
docker compose up -d --scale agent-worker=1
docker compose ps -a
curl.exe -fsS http://localhost:8000/ready
```

A healthy stack with cached images can demonstrate locally without calling an
external model. Do not rely on internet for the PPT or PDF. Avoid stopping Docker
or using `docker compose down -v`: removing volumes deletes stored run evidence.

## 4. Opening explanation: about 45 seconds

Say this in your own words:

> We are Pirate Hunter. Our project is LabelGuard, an asynchronous packaged-food
> label checking service. We support structured domestic retail breakfast-cereal
> specifications. A research agent chooses retrieval tools, and a separate
> verification agent checks the citations and recalculates the findings. The
> service returns cited findings or a human-review route. Today we are using the
> reproducible deterministic planner demo profile. The HTTP flow, durable queue,
> agents and verification all execute, while live external-LLM quality remains
> unmeasured. The final print decision belongs to a regulatory professional.

Show the team slide. Suggested speaking split, subject to your team's agreement:
Naveen presents the scope and live flow, Nishanth explains evidence and
evaluation, and Sateesh explains containers, reliability and load results. These
are proposed presentation roles, not claims about past contributions.

## 5. Exact 10–12 minute demonstration

### 0:00–1:00 — Team, scope and readiness

Show PPT slides 1–4 and `/ready`. Explain that HTTP 202 acknowledges receipt,
then the client polls. Show two distinct workers in `docker compose ps`.

### 1:00–3:00 — Qualifying protein example

1. In the app select **New label check**.
2. Under **Load a demonstration**, select **Protein claim · qualifying content**.
3. Explain the visible values: protein **6 g/100 g**, energy **376 kcal/100 g**,
   serving **40 g**. Expand **Full label & package specification** to show that
   the quick form is backed by a structured JSON request.
4. To force fresh research during repeated rehearsals, change
   `declarations.batch_number` inside the JSON to a new value such as
   `DEMO-29-OCT-A`, then click **Apply JSON to form**. Use another unique value
   next time. Leave the other valid fields unchanged.
5. Click **Check label**. Point out the run ID and processing stages. Very brief
   stages may pass before a viewer sees them; the trace records them.
6. Expect **Supported checks passed** in the UI and `clear-for-print` in JSON.
   Show `verified: true` and `print_authorized: false` in the result JSON.
7. Open the protein finding's citations. Explain the dependency: the labelling
   regulation covers the nutrition declaration, while the separate claims
   regulation supplies the threshold. Both sources matter.

Say: “With the example's supplied and reviewer-confirmed 54 g/day benchmark,
the source threshold is 5.4 g/100 g OR 2.7 g/100 kcal OR 5.4 g/serving. Six grams
per 100 g passes the first branch.” The 54 g/day value is an illustrative
assumption in this fixture. Do not present it as a universal RDA or an expert
approval of a real product.

### 3:00–4:00 — Insufficient protein

1. Select **Protein claim · insufficient content** and click **Check label**.
2. Expect **Revise & recheck** / `revise-and-recheck`.
3. Explain that **3 g/100 g**, **376 kcal/100 g**, **40 g/serve** fails every
   branch using the same illustrative benchmark. The service gives a concrete
   revision finding with citations rather than accepting the label's claim.

### 4:00–5:00 — Uncertainty and invalid data

1. Select **Outside corpus · human review**. Submit and show
   **Regulatory review required** / `regulatory-review` and the human action.
2. Select **Invalid nutrition · quarantine**. Submit and show the input error
   and quarantine record. If needed, use the API command below to show the
   HTTP status explicitly. Expected: **422**, `agent_started: false`.
3. Select **Prompt injection · quarantine**. Submit and show rejection before
   research starts. Explain that the detector is pattern based and limited.

The **Small package · exemption review** example is an optional second human
review case if asked about exemptions.

### 5:00–6:30 — Prove the agents and evidence path

1. Return to a valid result and click **Inspect run trace**. If changing examples has
   cleared the visible result, submit a new valid example or open its saved run
   ID in the API.
2. Show research events selecting `request_fields`, `corpus_search` and
   `clause_lookup`. Show a prompt version/digest and a tool observation.
3. Show the separate verification event and its successful independent check.
4. Open **Evidence library** and locate the source versions, hashes and the
   cross-regulation passages. Source PDFs are in `data/raw/`.
5. In Jaeger, choose the API service from the **Service** dropdown, select a
   recent lookback, click **Find Traces**, and open a recent run. Look for API,
   research, provider-stub and verification spans. Jaeger stores traces in
   memory, so use a fresh run after restarting it. The durable JSON run trace is
   the fallback if Jaeger has restarted.

### 6:30–8:30 — Evaluation and performance

Show PPT slides 10–12 and the corresponding raw files:

| Evidence | Explain |
|---|---|
| `output/evaluation/final-container-results.json` | Same 32 cases: v1 matches 14, v2 matches 32. Five are boundary rejects. v2 follows cross-regulation dependencies. |
| `docs/SLO.md` | Target declared before testing: p95 complete-run latency <= 15 seconds. This includes queue, research and verification. |
| `output/load/results.json` | At 8 users, one research worker: p95 24 s, 0.321 runs/s. Three workers: p95 8.9 s, 0.966 runs/s. |
| `output/load/cache/results.json` | Warm-cache p95 0.047 s vs 4.421 s without caching. Planner calls/run fall from 7 to 0. |

Explain that these are short, local tests with a 350 ms deterministic planner
delay. Three workers still miss the target at 20 users. The four quality metrics
measure provenance/policy consistency, not independent legal accuracy. Stub
provider cost is zero, so no paid-provider dollar saving was measured.

If asked to rerun evaluation, use this extra command after the main demonstration:

```powershell
docker compose exec -T api python -m labelguard.cli evaluate --output /app/output/evaluation/demo-results.json
```

If asked to prove tests, run `docker compose exec -T api pytest -q`. Saved
evidence records 21 passing tests; report the actual current output if rerunning.

### 8:30–10:00 — Operations, failure handling and repository

1. Open **Run activity** and then Grafana. Point out agent workload, end-to-end
   latency, retry/circuit behavior and explicitly synthetic stub usage. Existing
   history includes load/fault tests, so aggregate p95 can exceed the normal
   single-run timing. Historical stale worker entries remain in the audit store.
   Use `/ready` and Compose status to show the current workers are healthy.
2. Show `output/verification/fault-results.json`: an unsupported candidate fails
   verification and gets repaired. A provider outage opens the circuit and
   escalates safely. Present these as recorded fault exercises.
3. Open GitHub. Show `labelguard/`, `tests/`, `eval/`, `infra/`, `docs/` and
   `output/`. Show the README, reports and Actions check.
4. Close with the limits: supported cereal category, structured inputs, bounded
   policy coverage, independent professional decision and unmeasured live-model
   behavior.

Do not enable outage/fault controls during the main demo. Those exercises alter
the provider state and can disrupt subsequent examples. The detailed optional
fault rehearsal is in `docs/DEMO.md`, with recovery in `docs/RUNBOOK.md`.

## 6. Command-line backup when the UI is unavailable

These commands work in Windows PowerShell. Use `curl.exe` explicitly.

```powershell
# Receive a run ID immediately.
$accepted = curl.exe -sS -X POST http://localhost:8000/v1/runs -H 'Content-Type: application/json' --data-binary '@examples/valid-protein.json' | ConvertFrom-Json
$runId = $accepted.run_id
$runId

# Repeat until status is completed; the full rehearsal script polls automatically.
curl.exe -sS "http://localhost:8000/v1/runs/$runId"
curl.exe -sS "http://localhost:8000/v1/runs/$runId/trace"

# Show HTTP 422 and the quarantine body. -i prints response headers/status.
curl.exe -i -X POST http://localhost:8000/v1/runs -H 'Content-Type: application/json' --data-binary '@examples/malformed.json'
curl.exe -i -X POST http://localhost:8000/v1/runs -H 'Content-Type: application/json' --data-binary '@examples/prompt-injection.json'
```

Use Swagger's `POST /v1/runs`, **Try it out**, paste a complete example JSON and
**Execute** if you prefer clicks. Copy its returned `run_id` into
`GET /v1/runs/{run_id}`. Do not paste only the quick nutrition fields: the API
expects the complete request contract.

## 7. Likely questions and direct answers

| Question | Answer to rehearse |
|---|---|
| Which LLM is running? | The shown profile uses a deterministic HTTP planner stub. An OpenAI-compatible adapter exists, but a live external model has not been evaluated. |
| Is this agentic or a fixed script? | The LangGraph research loop chooses typed retrieval tools from observations. In today's fixture the planner's choices are deterministic. The worker/queue/tool flow executes for real. |
| Why a separate verifier? | It independently recomputes findings and re-resolves citations against pinned sources, rather than asking the same planner to approve itself. |
| Why FAISS and hashing? | It provides a reproducible local lexical baseline for a small corpus. Exact clause dependencies resolve the difficult claim linkage. It is not learned semantic retrieval. |
| Why async? | Submission returns a run ID immediately while separate workers process durable jobs. Polling avoids requiring the caller to expose a callback endpoint. |
| What if the model/provider fails? | Timeouts, two retries, a circuit breaker and safe escalation. No confident result substitutes for missing evidence. |
| What if a worker crashes? | Leases permit bounded reclaim. Ownership checks prevent stale publication, and expired run budgets can require review. |
| Does 100% mean all food labels are legally correct? | No. It means 32 fixture outcomes matched on this fixed set, including five rejects. It does not measure unseen cases or independent legal truth. |
| Is clear-for-print legal approval? | It is the assignment's advisory route code. The system always returns print_authorized:false. |
| What improvement did you measure? | Outcome matches improved from 14/32 to 32/32 after dependency-directed retrieval. Context relevance and recall improved. Groundedness, faithfulness and hallucination metrics stayed unchanged. |
| What was the scaling bottleneck? | Research-stage waiting and serial provider calls dominated in the tested range. SQLite could become a later limit, but its saturation was not measured. |
| Why no OCR/photo upload? | The assignment's supported input is structured text/package data. Artwork and OCR remain outside the implemented scope. |
| What remains? | Live-provider calibration, expert coverage and benchmark confirmation, wider rule coverage, authentication/retention and longer multi-host capacity tests. |

## 8. Recovery during the session

| Symptom | Action |
|---|---|
| Docker pipe/daemon connection error | Open Docker Desktop, wait for Linux engine startup, run `docker info`, then `docker compose up -d`. This error precedes application startup. |
| API works but a run stays queued | Check `/ready` and `docker compose ps -a`. Inspect `docker compose logs --tail=60 agent-worker verifier-worker`. Restart the failed worker, then submit a fresh request. |
| Provider issue | Inspect `docker compose logs --tail=60 provider-stub agent-worker`. Restore normal stub settings per runbook. Show the safe review result and explain the failure. |
| Repeated run finishes instantly | It may be a warm-cache hit. Change the batch number and resubmit to show fresh tool/agent work. |
| HTTP 429 | Pause repeated writes for the one-minute rate window. Normal limit is 30 writes/minute per peer. |
| Jaeger has no old trace | Submit a fresh request with a unique batch. Use the durable `/trace` JSON or saved trace files. |
| Internet/projector issue | Use the downloaded PPT/PDF and recorded screenshots/JSON. Clearly identify recorded evidence rather than describing it as a live run. |
| Need to stop after the session | Use `docker compose stop`. Do not delete named volumes. |

## 9. If they allow only five minutes

Opening/scope (30 s), valid protein + citations (90 s), insufficient protein
(45 s), review + quarantine (45 s), two workers/trace (30 s), evaluation/load
results and limitations (60 s). Leave the detailed monitoring and fault exercise
as questions or appendix material.

## 10. Last check before walking in

- Laptop charged, charger/adapter packed, Docker engine running.
- `/ready` succeeds and the main pass/fail examples run.
- GitHub link, PPT, PDF and complete ZIP are available locally.
- Team names/SRNs are correct and speaking hand-offs are agreed.
- Valid case, invalid case, human review and source citations are rehearsed.
- The planner fixture and metric limitations are explained accurately.
- No API keys or unrelated personal windows appear on the projected screen.
