import json
import logging
import os
import time
from contextlib import contextmanager
from prometheus_client import Counter, Gauge, Histogram
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from .config import settings
from . import store

STARTED = time.time()
RUNS = Counter("labelguard_runs_total", "Completed runs", ["agent", "outcome"])
CALLS = Counter("labelguard_tool_calls_total", "Tool calls", ["agent", "tool"])
ERRORS = Counter("labelguard_errors_total", "Errors", ["service", "kind"])
RETRIES = Counter("labelguard_provider_retries_total", "Model call retries", ["agent"])
TOKENS = Counter("labelguard_tokens_total", "Provider reported tokens", ["agent", "type"])
COST = Counter("labelguard_cost_total", "Configured provider cost", ["agent"])
LATENCY = Histogram("labelguard_step_seconds", "Agent step latency", ["agent", "step"])
END_TO_END = Histogram(
    "labelguard_run_seconds",
    "Submission to final result",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 30, 45, 60, 120, 300),
)
UPTIME = Gauge("labelguard_uptime_seconds", "Process uptime")
UPTIME.set_function(lambda: time.time() - STARTED)
BREAKER = Gauge("labelguard_provider_circuit_open", "Provider breaker open")
CACHE = Counter("labelguard_cache_total", "Whole-result cache", ["outcome"])
REJECTS = Counter("labelguard_quarantined_total", "Rejected inputs")
CORPUS_CHUNKS = Gauge("labelguard_corpus_chunks", "Indexed chunks")
CORPUS_BUILT = Gauge("labelguard_corpus_built_timestamp_seconds", "Index build timestamp")
CORPUS_RATE = Gauge("labelguard_corpus_chunks_per_second", "Index pipeline throughput")


def configure(service):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    provider = TracerProvider(
        resource=Resource.create({"service.name": service, "service.instance.id": str(os.getpid())})
    )
    if settings().otel_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings().otel_endpoint, timeout=3))
        )
    trace.set_tracer_provider(provider)


def log(kind, **values):
    logging.getLogger("labelguard").info(
        json.dumps({"timestamp": time.time(), "event": kind, **values}, default=str)
    )


@contextmanager
def step(run_id, agent, name, correlation_id):
    started = time.monotonic()
    tracer = trace.get_tracer("labelguard")
    with tracer.start_as_current_span(f"{agent}.{name}") as span:
        span.set_attribute("run.id", run_id)
        span.set_attribute("correlation.id", correlation_id)
        ok = False
        try:
            yield span
            ok = True
        finally:
            latency = time.monotonic() - started
            LATENCY.labels(agent, name).observe(latency)
            value = {
                "step": name,
                "latency_s": latency,
                "success": ok,
                "correlation_id": correlation_id,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            }
            store.event(run_id, agent, "step", value)
            log("agent_step", run_id=run_id, agent=agent, **value)
