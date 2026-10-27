"""Clearly labelled fixed-response planner emulator for reproducible tests/load only."""

import asyncio
import json
import time
from fastapi import FastAPI, HTTPException, Request, Response
from contextlib import asynccontextmanager
from opentelemetry import trace
from opentelemetry.propagate import extract
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .config import settings
from . import telemetry as t


@asynccontextmanager
async def lifespan(app):
    t.configure("labelguard-provider-stub")
    yield


app = FastAPI(title="LabelGuard deterministic provider stub", lifespan=lifespan)
fault = {"mode": "normal"}


def fixture_plan(context, version):
    if not context.get("fields_read"):
        return {
            "tool": "request_fields",
            "arguments": {"path": "nutrition"},
            "reason": "Read declared nutrition before deciding what evidence applies.",
        }
    if not context.get("has_mandatory"):
        return {
            "tool": "corpus_search",
            "arguments": {
                "query": "mandatory breakfast cereal declarations nutrition allergens",
                "family": "labelling",
            },
            "reason": "Retrieve applicable mandatory declarations.",
        }
    if version == "v2" and context.get("missing_ids"):
        missing = context["missing_ids"]
        clause = "AC-5.3" if "AC-5.3" in missing else missing[0]
        return {
            "tool": "clause_lookup",
            "arguments": {"clause_id": clause},
            "reason": "Inspect the cross-regulation dependency or unresolved provision: " + clause,
        }
    return {
        "tool": "finish",
        "arguments": {},
        "reason": "Return evidence to the independent verification agent.",
    }


@app.get("/health")
def health():
    return {"status": "ok", "mode": "deterministic_stub", "fault": fault["mode"]}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/fault/{mode}")
def set_fault(mode: str):
    if not settings().enable_faults:
        raise HTTPException(404)
    if mode not in ["normal", "unavailable", "timeout", "malformed"]:
        raise HTTPException(422)
    fault["mode"] = mode
    return fault


@app.post("/plan")
async def plan(request: Request):
    started = time.monotonic()
    body = await request.json()
    with trace.get_tracer("labelguard").start_as_current_span(
        "stub.planning_delay", context=extract(dict(request.headers))
    ) as span:
        span.set_attribute("run.id", request.headers.get("X-Run-ID", ""))
        span.set_attribute("correlation.id", request.headers.get("X-Correlation-ID", ""))
        await asyncio.sleep(settings().stub_delay_s)
    if fault["mode"] == "unavailable":
        raise HTTPException(503, "Injected provider outage")
    if fault["mode"] == "timeout":
        await asyncio.sleep(settings().provider_timeout_s + 2)
    if fault["mode"] == "malformed":
        return {"plan": {"tool": "shell", "arguments": {}}}
    result = fixture_plan(body["context"], body["prompt_version"])
    usage = {
        "prompt_tokens": (len(json.dumps(body)) + 3) // 4,
        "completion_tokens": (len(json.dumps(result)) + 3) // 4,
    }
    t.log(
        "stub_plan",
        correlation_id=request.headers.get("X-Correlation-ID"),
        run_id=request.headers.get("X-Run-ID"),
        latency_s=time.monotonic() - started,
    )
    return {"plan": result, "usage": usage, "usage_kind": "synthetic_stub"}
