"""Complete-run Locust transactions; API calls also retained as separate request stats."""

import json
import os
import time
import uuid
from pathlib import Path
import gevent
from locust import HttpUser, task, between, events

TEMPLATE = json.loads((Path(__file__).resolve().parents[1] / "examples/valid-protein.json").read_text())


class Analyst(HttpUser):
    wait_time = between(0.05, 0.1)

    @task
    def submit_and_poll(self):
        started = time.monotonic()
        failure = None
        payload = json.loads(json.dumps(TEMPLATE))
        # Disable result cache collisions without changing the legal scenario.
        if os.getenv("LOAD_REPEAT", "false") != "true":
            payload["declarations"]["batch_number"] = "LOAD-" + str(uuid.uuid4())
        response = self.client.post("/v1/runs", json=payload, name="submit", timeout=10)
        if response.status_code != 202:
            failure = RuntimeError("submit HTTP " + str(response.status_code))
        else:
            run_id = response.json()["run_id"]
            while time.monotonic() - started < 55:
                gevent.sleep(0.15)
                result = self.client.get("/v1/runs/" + run_id, name="poll", timeout=10)
                if result.status_code != 200:
                    failure = RuntimeError("poll HTTP " + str(result.status_code))
                    break
                value = result.json()
                if value["status"] == "failed":
                    failure = RuntimeError("run failed")
                    break
                if value["status"] == "completed":
                    answer = value["result"]
                    if answer["route"] != "clear-for-print" or not answer["verified"]:
                        failure = RuntimeError(
                            "run safely escalated or did not produce expected verified determination"
                        )
                    break
            else:
                failure = RuntimeError("completion polling timeout")
        events.request.fire(
            request_type="RUN",
            name="submission_to_result",
            response_time=(time.monotonic() - started) * 1000,
            response_length=0,
            exception=failure,
            context={},
        )
