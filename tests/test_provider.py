import time
import httpx
from labelguard.config import settings
from labelguard.provider import Provider, ProviderUnavailable


async def test_retries_open_breaker_and_skip_next_network_call(monkeypatch):
    s = settings()
    monkeypatch.setattr(s, "provider_url", "https://provider.invalid")
    monkeypatch.setattr(s, "provider_failure_threshold", 2)
    provider = Provider()
    await provider.client.aclose()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import pytest

    ctx = {"prompt_version": "v2", "prompt_sha256": "fixture"}
    with pytest.raises(ProviderUnavailable):
        await provider.plan(ctx, "fixture", "run", "cid", time.time() + 10)
    assert len(calls) == 2
    assert provider.open_until > time.monotonic()
    with pytest.raises(ProviderUnavailable, match="circuit"):
        await provider.plan(ctx, "fixture", "run", "cid", time.time() + 10)
    assert len(calls) == 2
    await provider.close()


async def test_provider_schema_cannot_invoke_arbitrary_tools(monkeypatch):
    monkeypatch.setattr(settings(), "provider_url", "https://provider.invalid")
    monkeypatch.setattr(settings(), "provider_retries", 0)
    provider = Provider()
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"plan": {"tool": "shell", "arguments": {}, "reason": "bad"}}
            )
        )
    )
    import pytest

    with pytest.raises(ProviderUnavailable):
        await provider.plan(
            {"prompt_version": "v2", "prompt_sha256": "fixture"}, "fixture", "run", "cid", time.time() + 2
        )
    await provider.close()


async def test_external_adapter_validates_plan_and_accounts_reported_usage(monkeypatch):
    import json
    from labelguard import store

    s = settings()
    monkeypatch.setattr(s, "provider_mode", "openai_compatible")
    monkeypatch.setattr(s, "provider_url", "https://provider.invalid/v1")
    monkeypatch.setattr(s, "provider_model", "runtime-test-fixture")
    monkeypatch.setattr(s, "prompt_cost_per_million", 2)
    monkeypatch.setattr(s, "completion_cost_per_million", 8)
    provider = Provider()
    await provider.client.aclose()

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "runtime-test-fixture"
        assert body["messages"][0]["role"] == "system"
        value = {
            "tool": "corpus_search",
            "arguments": {"query": "protein", "family": "claims"},
            "reason": "Fixture plan",
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(value)}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    plan = await provider.plan(
        {"prompt_version": "v2", "prompt_sha256": "fixture"},
        "prompt",
        "external-fixture",
        "cid",
        time.time() + 5,
    )
    assert plan.tool == "corpus_search"
    recorded = next(e["data"] for e in store.events("external-fixture") if e["kind"] == "model")
    assert recorded["prompt_tokens"] == 120
    assert abs(recorded["cost"] - 0.00048) < 1e-10
    assert recorded["usage_kind"] == "provider_reported"
    await provider.close()
