import asyncio
import hashlib
import time
from typing import TypedDict
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from opentelemetry.propagate import inject
from . import store, telemetry as t
from .config import settings
from .corpus import get_corpus
from .models import LabelRequest
from .provider import Provider, ProviderUnavailable
from .rules import MANDATORY, detect_claims, required_ids, evaluate, verify


class ResearchState(TypedDict, total=False):
    run_id: str
    correlation_id: str
    request: dict
    prompt_version: str
    deadline: float
    passages: list[dict]
    fields_read: bool
    steps: int
    tool_calls: int
    next_plan: dict
    finished: bool
    degraded_reason: str | None
    observations: list[dict]


def research_graph(provider: Provider):
    corpus, s = get_corpus(), settings()

    async def planner(state):
        version = state["prompt_version"]
        if version not in ("v1", "v2"):
            return {"finished": True, "degraded_reason": "Unsupported prompt version."}
        if (
            state["steps"] >= s.max_steps
            or state["tool_calls"] >= s.max_tool_calls
            or time.time() >= state["deadline"]
        ):
            return {"finished": True, "degraded_reason": "Agent step, tool-call or wall-clock limit reached."}
        prompt = (s.prompt_dir / f"{version}.md").read_text(encoding="utf-8")
        request = LabelRequest.model_validate(state["request"])
        have = {p["id"] for p in state["passages"]}
        context = {
            "prompt_version": version,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "category": request.category.value,
            "claims": detect_claims(request),
            "fields_read": state["fields_read"],
            "has_mandatory": set(MANDATORY) <= have,
            "missing_ids": sorted(set(required_ids(request)) - have),
            "evidence": [
                {"id": p["id"], "clause": p["clause"], "text": p["text"], "links": p.get("links", [])}
                for p in state["passages"]
            ],
            "observations": state["observations"][-3:],
        }
        with t.step(state["run_id"], "research", "plan", state["correlation_id"]):
            try:
                plan = await provider.plan(
                    context, prompt, state["run_id"], state["correlation_id"], state["deadline"]
                )
            except ProviderUnavailable as exc:
                return {"finished": True, "degraded_reason": str(exc), "steps": state["steps"] + 1}
        return {
            "next_plan": plan.model_dump(),
            "finished": plan.tool == "finish",
            "steps": state["steps"] + 1,
        }

    async def execute(state):
        if time.time() >= state["deadline"]:
            return {"finished": True, "degraded_reason": "Run deadline expired before a tool call."}
        request = state["request"]

        def request_fields(path: str = "nutrition"):
            """Read a validated request field: nutrition, package, declarations or rda_basis."""
            if path not in ["nutrition", "package", "declarations", "rda_basis"]:
                raise ValueError("Field is not on the read-only allowlist")
            return {"field": path, "value": request.get(path)}

        def corpus_search(query: str, family: str = "all"):
            """Search FAISS using LangChain. Families: all, labelling, claims, amendment_2026."""
            if len(query) > 400 or family not in ["all", "labelling", "claims", "amendment_2026"]:
                raise ValueError("Invalid corpus search arguments")
            return corpus.search(query, family)

        def clause_lookup(clause_id: str):
            """Retrieve an exact clause by its public corpus identifier."""
            if len(clause_id) > 80:
                raise ValueError("Invalid clause identifier")
            return corpus.lookup(clause_id)

        registry = {
            f.__name__: StructuredTool.from_function(f)
            for f in [request_fields, corpus_search, clause_lookup]
        }
        plan = state["next_plan"]
        tool = registry.get(plan["tool"])
        if tool is None:
            return {"finished": True, "degraded_reason": "The planner requested an unavailable tool."}
        with t.step(state["run_id"], "research", "execute_tool", state["correlation_id"]):
            try:
                async with asyncio.timeout(
                    min(s.tool_timeout_s, max(0.001, state["deadline"] - time.time()))
                ):
                    result = await asyncio.to_thread(tool.invoke, plan["arguments"])
            except Exception as exc:
                store.event(
                    state["run_id"],
                    "research",
                    "tool_error",
                    {"tool": plan["tool"], "error_type": type(exc).__name__},
                )
                return {"finished": True, "degraded_reason": "Tool failure: " + type(exc).__name__}
        t.CALLS.labels("research", plan["tool"]).inc()
        store.event(
            state["run_id"],
            "research",
            "tool",
            {
                "tool": plan["tool"],
                "arguments": plan["arguments"],
                "reason": plan["reason"],
                "result": result,
                "correlation_id": state["correlation_id"],
            },
        )
        passages = {p["id"]: p for p in state["passages"]}
        fields_read = state["fields_read"]
        if plan["tool"] == "request_fields":
            fields_read = True
            observation = {"field_read": result}
        else:
            passages.update({p["id"]: p for p in result})
            observation = {
                "retrieved_ids": [p["id"] for p in result],
                "links_discovered": sorted({link for p in result for link in p.get("links", [])}),
            }
        return {
            "passages": list(passages.values()),
            "fields_read": fields_read,
            "tool_calls": state["tool_calls"] + 1,
            "steps": state["steps"] + 1,
            "observations": state["observations"] + [observation],
        }

    graph = StateGraph(ResearchState)
    graph.add_node("plan", planner)
    graph.add_node("execute_tool", execute)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan", lambda x: "end" if x.get("finished") else "tool", {"end": END, "tool": "execute_tool"}
    )
    graph.add_conditional_edges(
        "execute_tool", lambda x: "end" if x.get("finished") else "plan", {"end": END, "plan": "plan"}
    )
    return graph.compile()


async def research(run, provider):
    state = {
        "run_id": run["id"],
        "correlation_id": run["correlation_id"],
        "request": run["request"],
        "prompt_version": run["prompt_version"],
        "deadline": run["created"] + settings().run_timeout_s,
        "passages": [],
        "fields_read": False,
        "steps": 0,
        "tool_calls": 0,
        "finished": False,
        "degraded_reason": None,
        "observations": [],
    }
    graph = research_graph(provider)
    async with asyncio.timeout(max(0.001, state["deadline"] - time.time())):
        state = await graph.ainvoke(state, config={"recursion_limit": settings().max_steps * 2 + 5})
    request = LabelRequest.model_validate(run["request"])
    state["candidate"] = evaluate(
        request, state["passages"], get_corpus(), run["prompt_version"], state.get("degraded_reason")
    )
    carrier = {}
    inject(carrier)
    state["trace_context"] = carrier
    return state


class VerificationState(TypedDict, total=False):
    run: dict
    bundle: dict
    candidate: dict
    passages: list[dict]
    problems: list[str]
    repairs: int
    verified: bool
    expected: dict
    result: dict


def verifier_graph():
    corpus = get_corpus()

    def validate(state):
        run, bundle = state["run"], state["bundle"]
        request = LabelRequest.model_validate(run["request"])
        with t.step(run["id"], "verification", "independent_check", run["correlation_id"]):
            # A passage bundle is untrusted at the hand-off boundary. Re-resolve every
            # byte against the pinned corpus before it can ground a determination.
            tampered = [p["id"] for p in state["passages"] if p != corpus.by_id.get(p["id"])]
            canonical = [p for p in state["passages"] if p == corpus.by_id.get(p["id"])]
            ok, problems, expected = verify(
                state["candidate"],
                request,
                canonical,
                corpus,
                run["prompt_version"],
                bundle.get("degraded_reason"),
            )
            if tampered:
                ok = False
                problems.append("Passage content differs from the pinned corpus: " + ",".join(tampered))
            missing = sorted(set(required_ids(request)) - {p["id"] for p in canonical})
            if missing:
                problems.append("Missing applicable provisions: " + ",".join(missing))
            store.event(
                run["id"],
                "verification",
                "verification",
                {
                    "passed": ok,
                    "problems": problems,
                    "missing_ids": missing,
                    "verifier_prompt_version": "verifier-v1",
                    "repair_attempt": state["repairs"],
                },
            )
        return {"verified": ok, "problems": problems, "expected": expected, "passages": canonical}

    async def repair(state):
        run = state["run"]
        if time.time() >= run["created"] + settings().run_timeout_s:
            return {"repairs": 1}
        request = LabelRequest.model_validate(run["request"])
        missing = sorted(set(required_ids(request)) - {p["id"] for p in state["passages"]})
        have = {p["id"]: p for p in state["passages"]}
        # Version 1 retries with labelling similarity; version 2 follows exact
        # cross-regulation identifiers. Both fail closed if evidence stays absent.
        with t.step(run["id"], "verification", "repair_search", run["correlation_id"]):
            for clause in missing[: settings().max_tool_calls]:
                remaining = run["created"] + settings().run_timeout_s - time.time()
                if remaining <= 0:
                    break
                if run["prompt_version"] == "v1":
                    query = "nutrition labelling " + clause
                    async with asyncio.timeout(min(settings().tool_timeout_s, remaining)):
                        found = await asyncio.to_thread(corpus.search, query, "labelling", 2)
                    args = {"query": query, "family": "labelling"}
                else:
                    async with asyncio.timeout(min(settings().tool_timeout_s, remaining)):
                        found = await asyncio.to_thread(corpus.lookup, clause)
                    args = {"clause_id": clause}
                have.update({p["id"]: p for p in found})
                t.CALLS.labels("verification", "repair_retrieval").inc()
                store.event(
                    run["id"],
                    "verification",
                    "tool",
                    {
                        "tool": "repair_retrieval",
                        "arguments": args,
                        "result": found,
                        "correlation_id": run["correlation_id"],
                    },
                )
        passages = list(have.values())
        candidate = evaluate(
            request, passages, corpus, run["prompt_version"], state["bundle"].get("degraded_reason")
        )
        return {"repairs": 1, "passages": passages, "candidate": candidate}

    def publish(state):
        run = state["run"]
        result = state["expected"]
        if not state["verified"]:
            result = evaluate(
                LabelRequest.model_validate(run["request"]),
                state["passages"],
                corpus,
                run["prompt_version"],
                "Independent verification could not confirm the candidate.",
            )
        # Coverage may remain incomplete even when the safe escalation itself verifies.
        store.event(
            run["id"],
            "verification",
            "publish",
            {
                "route": result["route"],
                "verified": True,
                "repairs": state["repairs"],
                "passage_ids": [p["id"] for p in state["passages"]],
            },
        )
        return {"result": result}

    graph = StateGraph(VerificationState)
    graph.add_node("verify", validate)
    graph.add_node("repair", repair)
    graph.add_node("publish", publish)
    graph.add_edge(START, "verify")
    graph.add_conditional_edges(
        "verify",
        lambda s: "repair" if s["problems"] and not s["repairs"] else "publish",
        {"repair": "repair", "publish": "publish"},
    )
    graph.add_edge("repair", "verify")
    graph.add_edge("publish", END)
    return graph.compile()


async def verification(run):
    bundle = run["research"]
    if time.time() > run["created"] + settings().run_timeout_s:
        bundle["degraded_reason"] = "The submission-to-result wall-clock budget expired before verification."
    state = {
        "run": run,
        "bundle": bundle,
        "candidate": bundle["candidate"],
        "passages": bundle["passages"],
        "repairs": 0,
    }
    output = await verifier_graph().ainvoke(state, config={"recursion_limit": 10})
    return output["result"]
