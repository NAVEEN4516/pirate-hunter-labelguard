import argparse
import asyncio
import os
import signal
import socket
import time
import uuid
from prometheus_client import start_http_server
from opentelemetry import context as otel_context, trace
from opentelemetry.propagate import extract
from . import store, telemetry as t
from .agents import research, verification
from .config import settings
from .corpus import get_corpus
from .models import LabelRequest
from .provider import Provider
from .rules import evaluate


async def serve(stage, metrics=True):
    s = settings()
    store.init_db()
    t.configure("labelguard-" + stage)
    corpus = get_corpus()
    t.CORPUS_CHUNKS.set(corpus.manifest["chunks"])
    t.CORPUS_BUILT.set(corpus.manifest["built_at"])
    if metrics:
        start_http_server(s.metrics_port)
    owner = f"{socket.gethostname()}-{os.getpid()}-{str(uuid.uuid4())[:6]}"
    started = time.time()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    provider = Provider()
    try:
        while not stop.is_set():
            store.heartbeat(owner, stage, started)
            job = store.claim_job(stage, owner)
            if not job:
                await asyncio.sleep(0.15)
                continue
            if job.get("exhausted"):
                store.event(
                    job["run_id"],
                    stage,
                    "job_exhausted",
                    {"attempts": job["attempts"], "print_authorized": False},
                )
                continue
            run = store.get_run(job["run_id"])
            carrier = (run.get("research") or {}).get("trace_context", {})
            if not carrier:
                submitted = [e["data"] for e in store.events(run["id"]) if e["kind"] == "submitted"]
                carrier = submitted[0].get("trace_context", {}) if submitted else {}
            token = otel_context.attach(extract(carrier))
            task_span = trace.get_tracer("labelguard").start_span(stage + ".task")
            task_token = otel_context.attach(trace.set_span_in_context(task_span))
            task_span.set_attribute("run.id", run["id"])
            task_span.set_attribute("correlation.id", run["correlation_id"])
            t.log(
                "job_claimed",
                agent=stage,
                run_id=run["id"],
                correlation_id=run["correlation_id"],
                attempt=job["attempts"],
            )
            try:
                if stage == "research":
                    bundle = await research(run, provider)
                    if s.enable_faults and any(
                        e["kind"] == "inject_unsupported" for e in store.events(run["id"])
                    ):
                        bundle["candidate"]["findings"][0]["explanation"] = (
                            "An unsupported invented claim was inserted for the verifier demonstration."
                        )
                        bundle["candidate"]["findings"][0]["citations"][0]["quote"] = "fabricated evidence"
                    store.handoff(job, bundle)
                    success = not bundle.get("degraded_reason")
                else:
                    result = await verification(run)
                    cacheable = not any(
                        f["requirement"] in ("service_reliability", "evidence_coverage")
                        for f in result["findings"]
                    )
                    store.finish(job, result, cacheable=cacheable)
                    t.END_TO_END.observe(time.time() - run["created"])
                    success = result["verified"]
                    sample = int(run["id"].replace("-", "")[:8], 16) / 0xFFFFFFFF
                    if sample < s.quality_sample_rate:
                        from .evaluation import score_live

                        score_live(run["id"])
                store.event(
                    run["id"], stage, "task_completed", {"success": success, "attempt": job["attempts"]}
                )
                t.RUNS.labels(stage, "success" if success else "degraded").inc()
            except Exception as exc:
                t.ERRORS.labels(stage, type(exc).__name__).inc()
                store.event(
                    run["id"],
                    stage,
                    "worker_error",
                    {"type": type(exc).__name__, "message": str(exc)[:300], "attempt": job["attempts"]},
                )
                # A normal exception is handled safely. A killed process leaves its lease
                # for another worker to reclaim, and cannot publish after lease expiry.
                fallback = evaluate(
                    LabelRequest.model_validate(run["request"]),
                    [],
                    corpus,
                    run["prompt_version"],
                    "Worker could not complete: " + type(exc).__name__,
                )
                store.finish(job, fallback, cacheable=False)
                store.event(
                    run["id"], stage, "task_completed", {"success": False, "attempt": job["attempts"]}
                )
                t.RUNS.labels(stage, "degraded").inc()
                t.END_TO_END.observe(time.time() - run["created"])
            finally:
                task_span.end()
                otel_context.detach(task_token)
                otel_context.detach(token)
    finally:
        await provider.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["research", "verification"])
    parser.add_argument("--no-metrics", action="store_true")
    args = parser.parse_args()
    asyncio.run(serve(args.stage, not args.no_metrics))


if __name__ == "__main__":
    main()
