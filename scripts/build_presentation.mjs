/** Build the editable project report in an Artifact presentation session. */
import fs from 'node:fs/promises';
import path from 'node:path';

export async function buildReport(p, root) {
  const C = {navy:'#142D3A', teal:'#087E83', ink:'#173745', muted:'#526977', paper:'#F7FAFB'};
  p.theme.defaultFont = 'Arial';
  const text=(s,value,x,y,w,h,size=28,color=C.ink,bold=false)=>{
    const a=s.shapes.add({geometry:'textbox',name:value.slice(0,50),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
    a.text=value;a.text.style={fontFamily:'Arial',fontSize:size,color,bold};return a;
  };
  const slide=(title,note='')=>{
    const s=p.slides.add();s.background.fill=C.paper;
    text(s,title,64,45,1152,105,44,C.navy,true);
    text(s,String(p.slides.items.length).padStart(2,'0'),1150,665,60,25,17,C.muted);
    s.speakerNotes.text=note;return s;
  };
  const note=(s,v)=>text(s,v,64,603,1120,54,20,C.muted);
  const rows=(s,items,y=180)=>items.forEach((a,i)=>{
    text(s,a[0],64,y+i*100,340,70,27,C.teal,true);
    text(s,a[1],430,y+i*100,770,80,27);
  });
  const table=(s,values,widths,y=180,height=350,size=25)=>{
    const t=s.tables.add({rows:values.length,columns:values[0].length,left:64,top:y,width:1152,height,columnWidths:widths,values});
    t.borders.assign({fill:'#D6E2E7',width:1,style:'solid'});
    for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
      const cell=t.getCell(r,c);cell.fill=r===0?C.navy:(r%2?'#FFFFFF':'#EDF4F5');
      cell.text.style={fontFamily:'Arial',fontSize:size,color:r===0?'#FFFFFF':C.ink,bold:r===0};
    }
    return t;
  };
  const screenshot=async(s,file,position)=>{
    const bytes=await fs.readFile(path.join(root,file));
    s.images.add({blob:new Uint8Array(bytes),contentType:'image/png',alt:'LabelGuard actual application screenshot',fit:'contain',position});
  };

  let s=p.slides.add();s.background.fill=C.navy;
  text(s,'PIRATE HUNTER',64,70,1100,45,27,'#78DAD1',true);
  text(s,'LabelGuard',64,185,1100,100,76,'#FFFFFF',true);
  text(s,'Packaged Food Label\nCompliance Check Service',64,315,1100,145,43,'#FFFFFF');
  text(s,'Mini Project 10\nML System Design & AgentOps\nPES University  /  28 October 2026',64,540,1100,110,25,'#B9D4DB');
  s.speakerNotes.text='Project report for UE24AM342AA5. Sources: README.md, docs/REPORT.md and the supplied MiniProject_10_Food_Label_Compliance.pdf. The demonstration uses a deterministic planner fixture, not a live external LLM.';

  s=slide('Project team','Team identities follow the user correction and supplied roster. No historical individual contribution claims are assigned. Source: docs/TEAM.md.');
  table(s,[['Team member','SRN'],['Naveen Prasad M','PES1UG24AM379'],['Nishanth Nag','PES1UG24AM381'],['Sateesh','PES1UG24AM397']],[680,472],190,330,30);
  note(s,'Team: Pirate Hunter. Course: UE24AM342AA5.');

  s=slide('Problem and supported scope','Source: docs/REPORT.md sections 1 and 2, docs/REQUIREMENTS.md. The route clear-for-print is retained only to meet the assignment interface. Every response has print_authorized:false.');
  rows(s,[['Problem','Label declarations and nutrition claims depend on different FSSAI regulations.'],['Input','Structured label and package data for domestic retail processed breakfast cereals.'],['Output','Cited findings with a supported-checks, revision or regulatory-review route.'],['Human decision','A regulatory professional decides print readiness. The service never authorises printing.']]);

  s=slide('Asynchronous service workflow','Source: labelguard/api.py, store.py, agents.py and worker.py. See docs/ARCHITECTURE.md for the deployment diagram. SQLite WAL provides the durable leased queue.');
  rows(s,[['01  Submit','FastAPI validates the request and returns a run ID with HTTP 202.'],['02  Research','A separate worker selects tools and retrieves applicable regulatory evidence.'],['03  Verify','Another worker re-resolves citations and recomputes the proposed findings.'],['04  Review','The browser polls for the verified result, exact citations and trace.']]);
  note(s,'Durable leases and atomic hand-off preserve work across worker restarts.');

  s=slide('Two agents with separate responsibilities','Source: labelguard/agents.py, provider.py, rules.py, prompts/v1.md, prompts/v2.md and prompts/verifier-v1.md. Research uses an HTTP planner. The verifier is deterministic and independent of the planner.');
  table(s,[['Responsibility','Research agent','Verification agent'],['Execution','LangGraph tool loop','Separate LangGraph graph'],['Evidence','Search and exact clause lookup','Re-resolve against pinned corpus'],['Decision','Build a candidate with citations','Recompute policy and arithmetic'],['Failure path','Bounded retry or escalation','One repair pass, then escalation']],[260,446,446],180,350,25);
  note(s,'Research tools: request_fields, corpus_search and clause_lookup.');

  s=slide('Pinned regulatory corpus','Official source URLs and SHA256 hashes are in data/sources.json. Labelling: https://www.fssai.gov.in/upload/uploadfiles/files/Comp_Labelling%20Display_Version%20VIII_09_09_2025.pdf . Claims: https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Advertising_Claims_Regulations_14_12_2022.pdf . Amendment: https://www.fssai.gov.in/docs/food-law/regulations/amendments/labelling-display/Notification%20dt%2024_03_2026_NRC.pdf . Gazette notifications prevail over compendia.');
  table(s,[['Source','Pinned version','Use'],['Labelling and Display 2020','VIII, 9 Sep 2025','Mandatory declarations'],['Advertising and Claims 2018','IV, 14 Dec 2022','Nutrition-claim conditions'],['First Amendment 2026','24 Mar 2026','Commences 1 Jul 2027']],[475,310,367],180,290,25);
  text(s,'146 chunks  /  19 curated clauses',64,505,1152,50,33,C.teal,true);
  note(s,'LangChain + FAISS with local lexical hashing embeddings. Dates from 1 July 2027 escalate.');

  s=slide('Protein claim: evidence across regulations','Sources: docs/DEMO.md, docs/REPORT.md section 2, data/clause_map.json and examples/valid-protein.json. Citations: LD 5(3)(b), pp10–11; AC 5(3), p4; AC Schedule I item11, p9; AC 2(1)(n), p2. The 54g/day benchmark is an illustrative supplied, reviewer-confirmed value, not a universal recommendation.');
  text(s,'For the illustrative 54 g/day benchmark, any one branch can qualify:',64,160,1152,65,27);
  table(s,[['Source-of-protein branch','Required protein'],['Per 100 g of solid food','5.4 g'],['Per 100 kcal','2.7 g'],['Per serving','5.4 g']],[740,412],240,275,27);
  note(s,'Example: 6 g/100 g passes the mass branch. At 3 g/100 g, 376 kcal/100 g and 40 g/serve, all fail.');

  s=slide('Guardrails and execution limits','Source: labelguard/models.py, guardrails.py, config.py, provider.py and docs/CONTRACTS.md. Injection/toxicity screening is pattern based and limited. It does not establish complete resistance to adversarial inputs.');
  rows(s,[['Before execution','Strict types, ranges, cross-field checks and text screening. Invalid inputs enter quarantine.'],['Tool boundary','Allowlisted tools and read-only field paths. Every citation must match a stored passage.'],['Research budget','24 steps, 12 tool calls, 5 s/tool and 8 s/provider attempt.'],['Recovery','Two provider retries, circuit breaker and a 45 s total run budget.']]);

  s=slide('Workbench and cited findings','Actual current viewport screenshot: output/demo/result-viewport.png. Sources: web/app.js and output/demo/rehearsal.json.');
  await screenshot(s,'output/demo/result-viewport.png',{left:64,top:155,width:1152,height:438});
  note(s,'The interface shows the recommendation, requirement findings and exact source passages.');

  s=slide('Prompt v2 matches all 32 fixed scenarios','Sources: output/evaluation/final-container-results.json and docs/REPORT.md section 5. The 32 cases include 27 answer scenarios and 5 rejects. Metrics measure citation provenance and consistency with the implemented policy. They do not establish independent legal truth or live-model generalisation.');
  table(s,[['Metric','v1','v2'],['Outcome matches','14 / 32','32 / 32'],['Groundedness','1.0000','1.0000'],['Context relevance','0.8522','1.0000'],['Faithfulness','1.0000','1.0000'],['Hallucination rate','0.0000','0.0000'],['Context recall','0.7541','1.0000']],[650,251,251],170,380,25);
  note(s,'v2 follows claim dependencies. Results use a deterministic fixture and shared policy-based metrics.');

  s=slide('Scaling meets the 15-second SLO at 8 users','Sources: docs/SLO.md, output/load/results.json and saved Locust CSVs. Target declared before measurement: p95 submission-to-final-result <=15s. Cache disabled, provider stub delay350ms, 30s arrival periods and up to50s drain. Small samples and rounded Locust histograms limit capacity conclusions.');
  table(s,[['Workers','Users','Runs','Runs/s','p95 (s)','SLO'],['1','2','11','0.332','6.2','Met'],['1','4','13','0.333','12.0','Met'],['1','8','17','0.321','24.0','Missed'],['3','4','31','0.963','5.5','Met'],['3','8','36','0.966','8.9','Met'],['3','20','46','0.993','20.0','Missed']],[180,170,170,205,205,222],165,385,25);
  note(s,'At 8 users, three research workers deliver 3.01× observed throughput. These are short local tests.');

  s=slide('Warm caching removes repeat planner calls','Sources: output/load/cache/results.json, docs/REPORT.md section7 and labelguard/store.py. Ten sequential runs per condition, prewarmed cache, priming excluded. p95 is the nearest-rank maximum with n=10. Cache TTL1h. Cache keys include request, corpus, prompt, verifier policy and provider configuration.');
  table(s,[['Measure','Cache disabled','Warm cache'],['p95 complete run','4.421 s','0.047 s'],['Planner calls/run','7','0'],['Actual provider cost','0','0']],[550,301,301],200,290,30);
  note(s,'Both conditions use the demo stub. Paid-model cost savings have not been measured.');

  s=slide('Operations and observability','Sources: infra/prometheus.yml, infra/grafana, labelguard/telemetry.py and output/verification/monitoring.json. The saved Jaeger trace connects API, research, provider stub and verification. Screenshot: output/demo/activity-viewport.png. Historical stale worker records and aggregate latency include earlier load/fault exercises. Current readiness is checked separately.');
  await screenshot(s,'output/demo/activity-viewport.png',{left:64,top:155,width:760,height:430});
  text(s,'Prometheus\nService metrics\n\nGrafana\n16 dashboard panels\n\nJaeger\nConnected service traces',865,175,350,400,27);
  note(s,'Seven long-running Compose services, plus one initialiser. Research workers scale independently.');

  s=slide('Tests and failure handling','Sources: output/verification/final-tests.xml, service-results.json, browser-results.json, fault-results.json, docs/INCIDENTS.md and docs/VERIFICATION.md. 21 tests passed in the Linux container. The external-provider adapter used MockTransport, not a paid live call.');
  table(s,[['Check','Observed result'],['Automated tests','21 passed'],['Browser acceptance','Submit, poll, citations, feedback and mobile passed'],['Tampered candidate','Verifier rejected it and repair succeeded'],['Provider outage','Circuit opened and the run escalated safely'],['Malformed or injected input','422 + quarantine, with no agent job created']],[410,742],180,365,26);
  note(s,'Actual incidents: registry pull retry recovered, and installed Edge resolved a missing test browser.');

  s=slide('Repository organisation','Sources: docs/REPOSITORY_GUIDE.md and README.md. GitHub repository: https://github.com/NAVEEN4516/pirate-hunter-labelguard . Source and verification commits were pushed and the first Actions workflow passed. Commits organise the delivery and do not claim historical individual contributions.');
  table(s,[['Path','Contents'],['labelguard/ and web/','Service, agents, policies and browser client'],['data/ and prompts/','Pinned regulations, clause map and versioned prompts'],['tests/, eval/ and loadtests/','Unit tests, fixed scenarios and Locust workload'],['infra/ and compose.yaml','Container orchestration and observability'],['docs/ and output/','Report, runbook, measured evidence and presentation']],[520,632],180,360,25);
  note(s,'README.md is the entry point. docs/DEMO.md contains the demonstration and viva guide.');

  s=slide('Demonstration and remaining work','Sources: docs/DEMO.md, docs/REQUIREMENTS.md and docs/REPORT.md. The live external-model adapter needs target-provider evaluation. Professional review remains required for product eligibility, exemptions, lab substantiation, licence authenticity, layout and Legal Metrology. No faculty approval is asserted.');
  rows(s,[['Run the service','docker compose up --build -d\nOpen http://localhost:8000'],['Demonstrate','Compare the protein pass/fail examples, then inspect citations and the agent trace.'],['Current limitation','Demonstration uses a deterministic HTTP planner stub. Live LLM quality is unmeasured.'],['Next work','Validate a real provider, expand expert-reviewed rules and run longer capacity tests.']]);

  s=slide('Report evidence and references','Official sources: data/sources.json (three FSSAI PDFs with URL, version and SHA256). Local sources: MiniProject_10_Food_Label_Compliance.pdf, docs/REPORT.md, docs/REQUIREMENTS.md, output/evaluation/final-container-results.json, output/load/results.json and output/verification/. All external facts and screenshots are cited in the relevant slide notes.');
  rows(s,[['Regulations','FSSAI Labelling and Display 2020, version VIII\nFSSAI Advertising and Claims 2018, version IV'],['Effective-date boundary','Labelling and Display First Amendment 2026\nNotified 24 March 2026, commences 1 July 2027'],['Measured evidence','Fixed evaluation results, raw Locust CSVs, browser screenshots and connected traces.'],['Companion documents','Final PDF report, requirement matrix, runbook, incident log and viva guide.']]);
  return {slideCount:p.slides.items.length};
}
