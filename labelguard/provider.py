"""Timeouts, backoff, per-process circuit breaker and bounded structured plans."""

import asyncio
import json
import time
import httpx
from opentelemetry.propagate import inject
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .config import settings
from . import store, telemetry as t


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["request_fields", "corpus_search", "clause_lookup", "finish"]
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(max_length=800)


class ProviderUnavailable(RuntimeError):
    pass


class Provider:
    def __init__(self):
        self.failures = 0
        self.open_until = 0.0
        self.client = httpx.AsyncClient(timeout=settings().provider_timeout_s)

    async def close(self):
        await self.client.aclose()

    async def plan(self, context, prompt, run_id, correlation_id, deadline):
        s = settings()
        if time.monotonic() < self.open_until:
            t.BREAKER.set(1)
            store.event(
                run_id,
                "research",
                "provider_circuit",
                {"state": "open", "cooldown_remaining_s": self.open_until - time.monotonic()},
            )
            raise ProviderUnavailable("Provider circuit is open; no unverified fallback answer is allowed.")
        if not s.provider_url:
            raise ProviderUnavailable("Provider URL is not configured.")
        # API keys are used only as HTTP credentials, never stored in events or prompts.
        headers = {"X-Correlation-ID": correlation_id, "X-Run-ID": run_id}
        inject(headers)
        if s.provider_api_key:
            headers["Authorization"] = "Bearer " + s.provider_api_key
        for attempt in range(s.provider_retries + 1):
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ProviderUnavailable("Run wall-clock budget exhausted.")
            started = time.monotonic()
            try:
                if s.provider_mode == "stub":
                    url = s.provider_url.rstrip("/") + "/plan"
                    body = {"context": context, "prompt_version": context["prompt_version"]}
                elif s.provider_mode == "openai_compatible":
                    if not s.provider_model:
                        raise ProviderUnavailable("External model identifier is not configured.")
                    url = s.provider_url.rstrip("/") + "/chat/completions"
                    body = {
                        "model": s.provider_model,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": json.dumps(context)},
                        ],
                        "temperature": 0,
                        "max_tokens": 350,
                        "response_format": {"type": "json_object"},
                    }
                else:
                    raise ProviderUnavailable("Unsupported provider mode.")
                async with asyncio.timeout(min(s.provider_timeout_s, remaining)):
                    response = await self.client.post(url, json=body, headers=headers)
                    response.raise_for_status()
                    value = response.json()
                    if s.provider_mode == "stub":
                        plan, usage = Plan.model_validate(value["plan"]), value.get("usage", {})
                    else:
                        plan = Plan.model_validate_json(value["choices"][0]["message"]["content"])
                        usage = value.get("usage", {})
                prompt_tokens, completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                cost = (
                    (prompt_tokens or 0) * s.prompt_cost_per_million
                    + (completion_tokens or 0) * s.completion_cost_per_million
                ) / 1_000_000
                self.failures, self.open_until = 0, 0
                t.BREAKER.set(0)
                t.TOKENS.labels("research", "prompt").inc(prompt_tokens or 0)
                t.TOKENS.labels("research", "completion").inc(completion_tokens or 0)
                t.COST.labels("research").inc(cost)
                store.event(
                    run_id,
                    "research",
                    "model",
                    {
                        "prompt_version": context["prompt_version"],
                        "prompt_sha256": context["prompt_sha256"],
                        "context": context,
                        "plan": plan.model_dump(),
                        "latency_s": time.monotonic() - started,
                        "retries": attempt,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "usage_available": prompt_tokens is not None and completion_tokens is not None,
                        "usage_kind": "synthetic_stub" if s.provider_mode == "stub" else "provider_reported",
                        "cost": cost,
                        "pricing": {
                            "prompt_per_million": s.prompt_cost_per_million,
                            "completion_per_million": s.completion_cost_per_million,
                        },
                    },
                )
                return plan
            except (httpx.HTTPError, TimeoutError, ValueError, KeyError, ProviderUnavailable) as exc:
                self.failures += 1
                t.ERRORS.labels("provider", type(exc).__name__).inc()
                store.event(
                    run_id,
                    "research",
                    "provider_failure",
                    {
                        "attempt": attempt + 1,
                        "error_type": type(exc).__name__,
                        "latency_s": time.monotonic() - started,
                        "correlation_id": correlation_id,
                    },
                )
                if self.failures >= s.provider_failure_threshold:
                    self.open_until = time.monotonic() + s.provider_cooldown_s
                    t.BREAKER.set(1)
                    store.event(
                        run_id,
                        "research",
                        "provider_circuit",
                        {"state": "open", "cooldown_s": s.provider_cooldown_s},
                    )
                    break
                if attempt < s.provider_retries:
                    t.RETRIES.labels("research").inc()
                    store.event(
                        run_id,
                        "research",
                        "provider_retry",
                        {"next_attempt": attempt + 2, "backoff_s": 0.2 * 2**attempt},
                    )
                    await asyncio.sleep(min(0.2 * 2**attempt, max(0, deadline - time.time())))
        raise ProviderUnavailable(
            "Provider retries exhausted or circuit opened. Manual regulatory review is required."
        )
