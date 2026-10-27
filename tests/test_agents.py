import time
import uuid
import pytest
from labelguard import store
from labelguard.agents import research, verification
from labelguard.evaluation import FixtureProvider
from labelguard.models import LabelRequest
from labelguard.rules import evaluate, required_ids, verify


def run_record(payload, version="v2"):
    return {
        "id": str(uuid.uuid4()),
        "request": payload,
        "created": time.time(),
        "correlation_id": "test",
        "prompt_version": version,
    }


async def test_cross_regulation_agent_path(payload):
    run = run_record(payload)
    run["research"] = await research(run, FixtureProvider())
    result = await verification(run)
    protein = next(f for f in result["findings"] if f["requirement"] == "source_protein")
    assert result["route"] == "clear-for-print"
    assert result["print_authorized"] is False
    assert {c["passage_id"] for c in protein["citations"]} == {"LD-5.3", "AC-5.3", "AC-PROTEIN", "AC-RDA"}
    assert any(
        e["data"].get("arguments", {}).get("clause_id") == "AC-PROTEIN"
        for e in store.events(run["id"])
        if e["kind"] == "tool"
    )


async def test_verifier_catches_and_repairs_fabricated_evidence(payload):
    run = run_record(payload)
    bundle = await research(run, FixtureProvider())
    bundle["candidate"]["findings"][0]["citations"][0]["quote"] = "Fabricated"
    run["research"] = bundle
    result = await verification(run)
    assert result["verified"]
    checks = [e for e in store.events(run["id"]) if e["kind"] == "verification"]
    assert checks[0]["data"]["passed"] is False
    assert checks[-1]["data"]["passed"] is True
    assert all(c["quote"] != "Fabricated" for f in result["findings"] for c in f["citations"])


async def test_tampered_passage_bundle_is_not_trusted(payload):
    run = run_record(payload)
    bundle = await research(run, FixtureProvider())
    bundle["passages"][0] = {**bundle["passages"][0], "text": "attacker content"}
    run["research"] = bundle
    result = await verification(run)
    checks = [e for e in store.events(run["id"]) if e["kind"] == "verification"]
    assert checks[0]["data"]["passed"] is False
    assert all("attacker content" != c["quote"] for f in result["findings"] for c in f["citations"])


def test_protein_alternatives_and_missing_rda(payload, corpus):
    request = LabelRequest.model_validate(payload)
    passages = [corpus.by_id[i] for i in required_ids(request)]
    payload["nutrition"]["protein_g"] = 3
    result = evaluate(LabelRequest.model_validate(payload), passages, corpus)
    assert next(f for f in result["findings"] if f["requirement"] == "source_protein")["status"] == "unmet"
    payload["nutrition"]["protein_g"] = 4
    payload["nutrition"]["energy_kcal"] = 120
    result = evaluate(LabelRequest.model_validate(payload), passages, corpus)
    assert next(f for f in result["findings"] if f["requirement"] == "source_protein")["status"] == "met"
    payload["rda_basis"] = None
    assert evaluate(LabelRequest.model_validate(payload), passages, corpus)["route"] == "regulatory-review"


def test_unsupported_authorisation_fails_verification(payload, corpus):
    request = LabelRequest.model_validate(payload)
    passages = [corpus.by_id[i] for i in required_ids(request)]
    candidate = evaluate(request, passages, corpus)
    candidate["print_authorized"] = True
    assert verify(candidate, request, passages, corpus, "v2")[0] is False


async def test_expired_run_never_returns_confident_result(payload):
    run = run_record(payload)
    run["research"] = await research(run, FixtureProvider())
    run["created"] -= 100
    result = await verification(run)
    assert result["route"] == "regulatory-review"


def test_lease_recovery_and_stale_owner_cannot_publish(payload, monkeypatch):
    from labelguard.config import settings

    monkeypatch.setattr(settings(), "lease_s", 2)
    rid, _ = store.submit(payload, "test", "cid", "key", "v2")
    first = store.claim_job("research", "worker-a")
    assert first["run_id"] == rid
    assert store.claim_job("research", "worker-b") is None
    with store.connection() as db:
        db.execute("UPDATE jobs SET lease_until=0")
    second = store.claim_job("research", "worker-b")
    assert second["attempts"] == 2
    with pytest.raises(RuntimeError, match="Lease lost"):
        store.handoff(first, {})
    store.handoff(second, {"candidate": {}})
    assert store.claim_job("verification", "verifier") is not None


def test_missing_evidence_always_escalates(payload, corpus):
    assert evaluate(LabelRequest.model_validate(payload), [], corpus)["route"] == "regulatory-review"
