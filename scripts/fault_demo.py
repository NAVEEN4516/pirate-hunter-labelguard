"""Run only with the local fault switches enabled. Save actual verifier/breaker evidence."""

import json
import os
import uuid
from pathlib import Path
import httpx
from verify_service import wait

root = Path("output/verification")
root.mkdir(parents=True, exist_ok=True)
base = os.environ.get("LG_TEST_API_URL", "http://127.0.0.1:8000")
stub = os.environ.get("LG_TEST_STUB_URL", "http://127.0.0.1:8010")
payload = json.loads(Path("examples/valid-protein.json").read_text())
evidence = {}
with httpx.Client(base_url=base, timeout=15) as client:
    payload["declarations"]["batch_number"] = "FAULT-" + str(uuid.uuid4())
    accepted = (
        client.post("/v1/runs", json=payload, headers={"X-Demo-Fault": "unsupported"})
        .raise_for_status()
        .json()
    )
    result = wait(client, accepted["run_id"])
    trace = client.get(f"/v1/runs/{accepted['run_id']}/trace").json()
    checks = [e["data"] for e in trace["events"] if e["kind"] == "verification"]
    assert checks[0]["passed"] is False, (
        "Enable LG_ENABLE_FAULTS=true on API and worker before this demonstration"
    )
    assert checks[-1]["passed"] is True
    evidence["unsupported_candidate"] = {"run": result, "trace": trace}
    print("Verifier caught unsupported candidate and repaired it:", accepted["run_id"])
    with httpx.Client(base_url=stub, timeout=15) as provider:
        provider.post("/fault/unavailable").raise_for_status()
        try:
            for number in range(2):
                payload["declarations"]["batch_number"] = "OUTAGE-" + str(uuid.uuid4())
                accepted = client.post("/v1/runs", json=payload).raise_for_status().json()
                result = wait(client, accepted["run_id"])
                trace = client.get(f"/v1/runs/{accepted['run_id']}/trace").json()
                assert result["result"]["route"] == "regulatory-review"
                assert any(e["kind"] == "provider_circuit" for e in trace["events"])
                evidence[f"provider_outage_{number + 1}"] = {"run": result, "trace": trace}
                print("Provider outage -> regulatory review; circuit evidence recorded:", accepted["run_id"])
        finally:
            provider.post("/fault/normal").raise_for_status()
(root / "fault-results.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print("Actual fault evidence saved. Provider restored; breaker cooldown still applies.")
