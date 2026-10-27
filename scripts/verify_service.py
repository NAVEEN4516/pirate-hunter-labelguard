"""Exercise real HTTP submission -> durable queues -> both agents -> result."""

import json
import os
import time
import uuid
from pathlib import Path
import httpx

BASE = os.environ.get("LG_TEST_API_URL", "http://127.0.0.1:8000")
OUT = Path("output/verification")
OUT.mkdir(parents=True, exist_ok=True)


def wait(client, run_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = client.get(f"/v1/runs/{run_id}").raise_for_status().json()
        if value["status"] in ("completed", "failed"):
            return value
        time.sleep(0.2)
    raise TimeoutError("Real service did not complete within 60 seconds")


def main():
    records = []
    with httpx.Client(base_url=BASE, timeout=15) as client:
        client.get("/ready").raise_for_status()
        for name, route in [
            ("valid-protein", "clear-for-print"),
            ("insufficient-protein", "revise-and-recheck"),
            ("out-of-scope", "regulatory-review"),
            ("small-pack", "regulatory-review"),
        ]:
            payload = json.loads(Path(f"examples/{name}.json").read_text())
            payload["declarations"]["batch_number"] += "-" + str(uuid.uuid4())[:8]
            submit = client.post("/v1/runs", json=payload, headers={"X-Correlation-ID": "verify-" + name})
            assert submit.status_code == 202, submit.text
            value = wait(client, submit.json()["run_id"])
            assert value["status"] == "completed", value
            assert value["result"]["route"] == route, value
            assert value["result"]["verified"] and value["result"]["print_authorized"] is False
            trace = client.get(f"/v1/runs/{value['run_id']}/trace").raise_for_status().json()
            assert any(e["agent"] == "research" for e in trace["events"])
            assert any(e["agent"] == "verification" and e["kind"] == "verification" for e in trace["events"])
            for finding in value["result"]["findings"]:
                for citation in finding["citations"]:
                    passage = client.get("/v1/passages/" + citation["passage_id"]).raise_for_status().json()
                    assert passage["text"] == citation["quote"]
            records.append({"example": name, "submission": submit.json(), "run": value})
            (OUT / f"{name}-trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
            print(name, value["result"]["route"], round(value["latency_s"], 3), "seconds", value["run_id"])
        for name in ["malformed", "prompt-injection"]:
            before = client.get("/v1/dashboard").json()["counts"]
            response = client.post("/v1/runs", json=json.loads(Path(f"examples/{name}.json").read_text()))
            assert response.status_code == 422
            assert response.json()["agent_started"] is False
            after = client.get("/v1/dashboard").json()["counts"]
            assert before == after
            records.append(
                {"example": name, "rejection": response.json(), "run_counts_unchanged": before == after}
            )
            print(name, "quarantined; no run created")
        first = records[0]["run"]
        response = client.post(
            f"/v1/runs/{first['run_id']}/feedback",
            json={
                "satisfactory": True,
                "reason": "Development verification: citations resolve and protein arithmetic agrees.",
            },
        )
        assert response.status_code == 201
        (OUT / "service-results.json").write_text(
            json.dumps({"checked_at": time.time(), "records": records, "feedback_saved": True}, indent=2),
            encoding="utf-8",
        )
    print("Live service verification passed")


if __name__ == "__main__":
    main()
