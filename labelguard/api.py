import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from opentelemetry import trace
from opentelemetry.propagate import inject
from . import store, telemetry as t
from .config import settings
from .corpus import get_corpus
from .guardrails import inspect_input
from .models import Feedback, LabelRequest


@asynccontextmanager
async def lifespan(app):
    store.init_db()
    t.configure("labelguard-api")
    corpus = get_corpus()
    t.CORPUS_CHUNKS.set(corpus.manifest["chunks"])
    t.CORPUS_BUILT.set(corpus.manifest["built_at"])
    t.CORPUS_RATE.set(corpus.manifest["chunks_per_second"])
    yield


app = FastAPI(
    title="Pirate Hunter | LabelGuard",
    version="1.0.0",
    lifespan=lifespan,
    description="Asynchronous advisory compliance findings for domestic packaged breakfast cereals. print_authorized is always false. Local academic deployment; do not expose publicly without authentication.",
)
WEB = Path(__file__).resolve().parents[1] / "web"
if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


def client_id(request):
    return request.client.host if request.client else "local"


@app.middleware("http")
async def context_and_limits(request, call_next):
    cid = request.headers.get("X-Correlation-ID", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", cid):
        cid = str(uuid.uuid4())
    request.state.correlation_id = cid
    started = time.monotonic()
    if request.method in ("POST", "PUT", "PATCH"):
        if not store.limit(client_id(request)):
            return JSONResponse(
                status_code=429,
                content={"detail": "Per-client rate limit exceeded", "correlation_id": cid},
                headers={"Retry-After": "60"},
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > settings().max_body_bytes:
                qid = store.quarantine(
                    {"body": "omitted: over size limit"},
                    [{"loc": ["body"], "msg": "Request exceeds 64 KiB"}],
                    client_id(request),
                    cid,
                )
                t.REJECTS.inc()
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": "Request body too large",
                        "quarantine_id": qid,
                        "agent_started": False,
                    },
                )
        request._body = bytes(body)
    with trace.get_tracer("labelguard").start_as_current_span(
        request.method + " " + request.url.path
    ) as span:
        span.set_attribute("correlation.id", cid)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
    t.log(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_s=time.monotonic() - started,
        correlation_id=cid,
    )
    return response


@app.exception_handler(RequestValidationError)
async def rejected(request, exc):
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    qid = store.quarantine(exc.body, errors, client_id(request), request.state.correlation_id)
    t.REJECTS.inc()
    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "quarantine_id": qid,
            "agent_started": False,
            "correlation_id": request.state.correlation_id,
        },
    )


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "labelguard-api", "version": "1.0.0"}


@app.get("/ready")
def ready():
    with store.connection() as db:
        active = [
            r[0]
            for r in db.execute(
                "SELECT DISTINCT stage FROM heartbeats WHERE timestamp > ?",
                (time.time() - max(10, settings().run_timeout_s + 5),),
            )
        ]
    good = set(active) >= {"research", "verification"}
    return JSONResponse(
        status_code=200 if good else 503,
        content={
            "ready": good,
            "active_worker_stages": active,
            "corpus_version": get_corpus().manifest["version"],
        },
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/contract")
def contract():
    return LabelRequest.model_json_schema()


@app.get("/v1/info")
def info():
    return {
        "mode": settings().provider_mode,
        "prompt_version": settings().prompt_version,
        "print_authorized": False,
    }


@app.get("/v1/examples/{name}")
def example(name: str):
    if name not in [
        "valid-protein",
        "insufficient-protein",
        "small-pack",
        "out-of-scope",
        "prompt-injection",
        "malformed",
    ]:
        raise HTTPException(404, "Example not found")
    return json.loads(
        (Path(__file__).resolve().parents[1] / "examples" / (name + ".json")).read_text(encoding="utf-8")
    )


@app.get("/v1/corpus")
def corpus():
    return get_corpus().manifest


@app.get("/v1/passages/{passage_id}")
def passage(passage_id: str):
    found = get_corpus().lookup(passage_id)
    if not found:
        raise HTTPException(404, "Passage not found")
    return found[0]


@app.post("/v1/runs", status_code=202)
def submit(payload: LabelRequest, request: Request):
    value = payload.model_dump(mode="json")
    errors = inspect_input(value)
    if errors:
        fields = [{"loc": ["body", "free_text"], "msg": e, "type": "guardrail"} for e in errors]
        qid = store.quarantine(value, fields, client_id(request), request.state.correlation_id)
        t.REJECTS.inc()
        return JSONResponse(
            status_code=422, content={"detail": fields, "quarantine_id": qid, "agent_started": False}
        )
    prompt = settings().prompt_version
    if prompt not in ("v1", "v2"):
        raise HTTPException(503, "A supported prompt version must be configured")
    key = store.cache_key(value, get_corpus().manifest["version"], prompt)
    run_id, cached = store.submit(value, client_id(request), request.state.correlation_id, key, prompt)
    if request.headers.get("X-Demo-Fault") == "unsupported" and settings().enable_faults:
        store.event(run_id, "api", "inject_unsupported", {"enabled": True})
    carrier = {}
    inject(carrier)
    store.event(
        run_id,
        "api",
        "submitted",
        {
            "cached": cached,
            "correlation_id": request.state.correlation_id,
            "prompt_version": prompt,
            "trace_context": carrier,
        },
    )
    t.CACHE.labels("hit" if cached else "miss").inc()
    if cached:
        t.END_TO_END.observe(time.time() - store.get_run(run_id)["created"])
    return {
        "run_id": run_id,
        "status": "completed" if cached else "queued",
        "status_url": f"/v1/runs/{run_id}",
        "cached": cached,
        "correlation_id": request.state.correlation_id,
    }


@app.get("/v1/runs/{run_id}")
def run_status(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    events = store.events(run_id)
    model_calls = [e["data"] for e in events if e["kind"] == "model"]
    return {
        "run_id": run_id,
        "status": run["status"],
        "submitted_at": run["created"],
        "updated_at": run["updated"],
        "latency_s": (run["updated"] if run["status"] in ("completed", "failed") else time.time())
        - run["created"],
        "cached": bool(run["cached"]),
        "correlation_id": run["correlation_id"],
        "result": run["result"],
        "usage": {
            "prompt_tokens": sum(x.get("prompt_tokens") or 0 for x in model_calls),
            "completion_tokens": sum(x.get("completion_tokens") or 0 for x in model_calls),
            "cost": sum(x.get("cost") or 0 for x in model_calls),
            "model_calls": len(model_calls),
            "usage_available": all(x.get("usage_available", False) for x in model_calls),
            "cost_complete": all(x.get("usage_available", False) for x in model_calls)
            and not any(e["kind"] == "provider_failure" for e in events),
            "usage_kind": "synthetic_stub" if settings().provider_mode == "stub" else "provider_reported",
            "cache_hit_cost": 0 if run["cached"] else None,
        },
    }


@app.get("/v1/runs/{run_id}/trace")
def run_trace(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {"run_id": run_id, "correlation_id": run["correlation_id"], "events": store.events(run_id)}


@app.post("/v1/runs/{run_id}/feedback", status_code=201)
def feedback(run_id: str, payload: Feedback):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] != "completed":
        raise HTTPException(409, "Feedback requires a completed result")
    if inspect_input(payload.model_dump()):
        raise HTTPException(422, "Feedback text failed the input filter")
    store.add_feedback(run_id, payload)
    return {"saved": True}


@app.get("/v1/dashboard")
def dashboard():
    return store.dashboard()


@app.get("/v1/quarantine/{quarantine_id}")
def quarantined(quarantine_id: str):
    with store.connection() as db:
        row = db.execute(
            "SELECT id,created,errors,correlation_id FROM quarantine WHERE id=?", (quarantine_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Quarantine record not found")
    return {**dict(row), "errors": json.loads(row["errors"]), "agent_started": False}


def export_openapi(path):
    Path(path).write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
