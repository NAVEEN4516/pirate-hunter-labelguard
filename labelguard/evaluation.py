"""Reproducible policy/evidence metrics, not a model-quality or legal-validity claim."""

import asyncio
import json
import statistics
import tempfile
import time
import uuid
from pathlib import Path
from pydantic import ValidationError
from . import store
from .agents import research, verification
from .config import settings
from .corpus import get_corpus
from .guardrails import inspect_input
from .models import LabelRequest
from .provider import Plan
from .rules import verify, required_ids
from .stub import fixture_plan


class FixtureProvider:
    async def plan(self, context, prompt, run_id, correlation_id, deadline):
        return Plan.model_validate(fixture_plan(context, context["prompt_version"]))


def scores(result, request, passages, corpus, expected_passages):
    assertions = [f for f in result["findings"] if f["status"] in ("met", "unmet")]
    canonical = {p["id"]: p for p in passages if corpus.by_id.get(p["id"]) == p}
    grounded = sum(
        bool(f["citations"])
        and all(
            c["passage_id"] in canonical and corpus.citation(canonical[c["passage_id"]]) == c
            for c in f["citations"]
        )
        for f in assertions
    )
    groundedness = grounded / len(assertions) if assertions else 1.0
    cited = {c["passage_id"] for f in result["findings"] for c in f["citations"]}
    # Relevant context is the union of expert scenario gold and applicable checklist
    # provisions. Raw page chunks that do not resolve to a needed provision count as noise.
    relevant = set(expected_passages) | set(required_ids(request))
    retrieved = set(canonical)
    relevance = len(retrieved & relevant) / len(retrieved) if retrieved else 0
    independent = verify(result, request, passages, corpus, result["prompt_version"])[2]
    expected_map = {f["requirement"]: f for f in independent["findings"]}
    faithful = sum(f == expected_map.get(f["requirement"]) for f in result["findings"])
    faithfulness = faithful / len(result["findings"]) if result["findings"] else 1.0
    hallucinations = sum(
        not f["citations"]
        or any(
            c["passage_id"] not in canonical or corpus.citation(canonical[c["passage_id"]]) != c
            for c in f["citations"]
        )
        for f in assertions
    )
    return {
        "groundedness": groundedness,
        "context_relevance": relevance,
        "faithfulness": faithfulness,
        "hallucination_rate": hallucinations / len(assertions) if assertions else 0.0,
        "context_recall": len(retrieved & relevant) / len(relevant) if relevant else 1.0,
        "assertions": len(assertions),
        "retrieved_passages": len(retrieved),
        "cited_passages": len(cited),
    }


async def evaluate_all():
    scenarios = json.loads(Path("eval/scenarios.json").read_text(encoding="utf-8"))
    corpus = get_corpus()
    output = {
        "measured_at": time.time(),
        "method": "In-process LangGraph research and verification with deterministic planner fixture; no external LLM. Outcomes checked against fixed hand-authored gold. Faithfulness is deterministic policy consistency, not independent semantic judgement.",
        "corpus_version": corpus.manifest["version"],
        "variants": {},
    }
    for version in ["v1", "v2"]:
        rows = []
        for scenario in scenarios:
            started = time.monotonic()
            try:
                request = LabelRequest.model_validate(scenario["request"])
                errors = inspect_input(request.model_dump(mode="json"))
                if errors:
                    raise ValueError("Guardrail reject")
            except (ValidationError, ValueError):
                rows.append({"id": scenario["id"], "correct": scenario["reject"], "rejected": True})
                continue
            run = {
                "id": str(uuid.uuid4()),
                "request": request.model_dump(mode="json"),
                "created": time.time(),
                "correlation_id": "eval-" + str(uuid.uuid4()),
                "prompt_version": version,
            }
            bundle = await research(run, FixtureProvider())
            run["research"] = bundle
            result = await verification(run)
            ids = next(
                e["data"]["passage_ids"] for e in reversed(store.events(run["id"])) if e["kind"] == "publish"
            )
            passages = [corpus.by_id[i] for i in ids]
            metric = scores(result, request, passages, corpus, scenario["supporting_passages"])
            observed = next(
                (
                    f["status"]
                    for f in result["findings"]
                    if f["requirement"] == scenario["expected_requirement"]
                ),
                None,
            )
            correct = (
                not scenario["reject"]
                and result["route"] == scenario["expected_route"]
                and (not scenario["expected_requirement"] or observed == scenario["expected_status"])
            )
            rows.append(
                {
                    "id": scenario["id"],
                    "correct": correct,
                    "route": result["route"],
                    "expected_route": scenario["expected_route"],
                    "requirement_status": observed,
                    "expected_status": scenario["expected_status"],
                    "latency_s": time.monotonic() - started,
                    **metric,
                }
            )
        metrics_rows = [r for r in rows if not r.get("rejected")]
        means = {
            m: statistics.mean(r[m] for r in metrics_rows)
            for m in [
                "groundedness",
                "context_relevance",
                "faithfulness",
                "hallucination_rate",
                "context_recall",
            ]
        }
        output["variants"][version] = {
            "scenario_count": len(rows),
            "answer_scenarios": len(metrics_rows),
            "correct": sum(r["correct"] for r in rows),
            "accuracy": sum(r["correct"] for r in rows) / len(rows),
            "metrics": means,
            "rows": rows,
        }
    return output


def run_evaluation(path):
    original = settings().data_dir
    # Evaluation does not pollute live runs, feedback or quality charts.
    with tempfile.TemporaryDirectory(prefix="labelguard-eval-") as temp:
        settings().data_dir = Path(temp)
        store.init_db()
        try:
            result = asyncio.run(evaluate_all())
        finally:
            settings().data_dir = original
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for version, values in result["variants"].items():
        print(version, values["correct"], "/", values["scenario_count"], values["metrics"])
    print("Measured results:", target)


def score_live(run_id):
    run, corpus = store.get_run(run_id), get_corpus()
    events = store.events(run_id)
    published = [e["data"] for e in events if e["kind"] == "publish"]
    if not published:
        return
    request = LabelRequest.model_validate(run["request"])
    passages = [corpus.by_id[i] for i in published[-1]["passage_ids"] if i in corpus.by_id]
    metric = scores(run["result"], request, passages, corpus, required_ids(request))
    with store.connection() as db:
        db.execute("INSERT OR REPLACE INTO quality VALUES(?,?,?)", (run_id, time.time(), json.dumps(metric)))
