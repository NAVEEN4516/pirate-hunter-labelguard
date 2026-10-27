"""SQLite WAL state + durable leased queues. Every hand-off is one transaction."""

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import settings


def dumps(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


@contextmanager
def connection():
    db = sqlite3.connect(settings().db_path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    try:
        yield db
    finally:
        db.close()


def init_db():
    with connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, client TEXT NOT NULL, request TEXT NOT NULL,
          status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
          result TEXT, research TEXT, cache_key TEXT, cached INTEGER DEFAULT 0,
          prompt_version TEXT NOT NULL, correlation_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          stage TEXT NOT NULL, state TEXT DEFAULT 'queued', owner TEXT,
          lease_until REAL DEFAULT 0, attempts INTEGER DEFAULT 0,
          UNIQUE(run_id, stage));
        CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(stage,state,lease_until);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          timestamp REAL NOT NULL, agent TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_run ON events(run_id,id);
        CREATE TABLE IF NOT EXISTS quarantine (
          id TEXT PRIMARY KEY, created REAL NOT NULL, client TEXT NOT NULL,
          request TEXT NOT NULL, errors TEXT NOT NULL, correlation_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback (
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          satisfactory INTEGER NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, result TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS limits (client TEXT NOT NULL, window INTEGER NOT NULL,
          count INTEGER NOT NULL, PRIMARY KEY(client,window));
        CREATE TABLE IF NOT EXISTS heartbeats (worker TEXT PRIMARY KEY, stage TEXT, timestamp REAL, started REAL);
        CREATE TABLE IF NOT EXISTS quality (run_id TEXT PRIMARY KEY, created REAL, scores TEXT);
        """)


def cache_key(request, corpus_version, prompt_version):
    s = settings()
    prompt_path = s.prompt_dir / f"{prompt_version}.md"
    prompt_hash = hashlib.sha256(prompt_path.read_bytes()).hexdigest() if prompt_path.exists() else "missing"
    verifier_hash = hashlib.sha256((s.prompt_dir / "verifier-v1.md").read_bytes()).hexdigest()
    from pathlib import Path

    policy_hash = hashlib.sha256(Path(__file__).with_name("rules.py").read_bytes()).hexdigest()
    envelope = [
        request,
        corpus_version,
        prompt_version,
        prompt_hash,
        verifier_hash,
        policy_hash,
        s.provider_mode,
        s.provider_url,
        s.provider_model,
    ]
    return hashlib.sha256(dumps(envelope).encode()).hexdigest()


def limit(client):
    window = int(time.time() // 60)
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM limits WHERE window < ?", (window - 2,))
        db.execute(
            "INSERT INTO limits VALUES(?,?,1) ON CONFLICT(client,window) DO UPDATE SET count=count+1",
            (client, window),
        )
        count = db.execute(
            "SELECT count FROM limits WHERE client=? AND window=?", (client, window)
        ).fetchone()[0]
        db.commit()
    return count <= settings().rate_limit_per_minute


def quarantine(request, errors, client, correlation_id):
    qid = str(uuid.uuid4())
    with connection() as db:
        db.execute(
            "INSERT INTO quarantine VALUES(?,?,?,?,?,?)",
            (qid, time.time(), client, dumps(request), dumps(errors), correlation_id),
        )
    return qid


def submit(request, client, correlation_id, key, prompt_version):
    run_id, now = str(uuid.uuid4()), time.time()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cached = (
            db.execute("SELECT result FROM cache WHERE key=? AND expires>?", (key, now)).fetchone()
            if settings().cache_enabled
            else None
        )
        db.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                client,
                dumps(request),
                "completed" if cached else "queued",
                now,
                now,
                cached[0] if cached else None,
                None,
                key,
                int(bool(cached)),
                prompt_version,
                correlation_id,
            ),
        )
        if not cached:
            db.execute("INSERT INTO jobs(run_id,stage) VALUES(?, 'research')", (run_id,))
        db.commit()
    return run_id, bool(cached)


def get_run(run_id):
    with connection() as db:
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        return None
    value = dict(row)
    for key in ["request", "result", "research"]:
        if value[key]:
            value[key] = json.loads(value[key])
    return value


def event(run_id, agent, kind, data):
    with connection() as db:
        db.execute(
            "INSERT INTO events(run_id,timestamp,agent,kind,data) VALUES(?,?,?,?,?)",
            (run_id, time.time(), agent, kind, dumps(data)),
        )


def events(run_id):
    with connection() as db:
        rows = db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [{**dict(row), "data": json.loads(row["data"])} for row in rows]


def claim_job(stage, owner):
    now = time.time()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM jobs WHERE stage=? AND (state='queued' OR (state='running' AND lease_until<?)) ORDER BY id LIMIT 1",
            (stage, now),
        ).fetchone()
        if not row:
            db.rollback()
            return None
        if row["attempts"] >= settings().max_job_attempts:
            db.execute("UPDATE jobs SET state='exhausted' WHERE id=?", (row["id"],))
            db.execute("UPDATE runs SET status='failed',updated=? WHERE id=?", (now, row["run_id"]))
            db.commit()
            return {**dict(row), "exhausted": True}
        db.execute(
            "UPDATE jobs SET state='running',owner=?,lease_until=?,attempts=attempts+1 WHERE id=?",
            (owner, now + settings().lease_s, row["id"]),
        )
        db.execute("UPDATE runs SET status=?,updated=? WHERE id=?", (stage, now, row["run_id"]))
        db.commit()
    return {**dict(row), "owner": owner, "attempts": row["attempts"] + 1}


def handoff(job, research):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE jobs SET state='done' WHERE id=? AND owner=? AND state='running' AND lease_until>?",
            (job["id"], job["owner"], time.time()),
        ).rowcount
        if not changed:
            db.rollback()
            raise RuntimeError("Lease lost before research hand-off")
        db.execute(
            "UPDATE runs SET research=?,status='verification-queued',updated=? WHERE id=?",
            (dumps(research), time.time(), job["run_id"]),
        )
        db.execute("INSERT OR IGNORE INTO jobs(run_id,stage) VALUES(?, 'verification')", (job["run_id"],))
        db.commit()


def finish(job, result, cacheable=False):
    now = time.time()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE jobs SET state='done' WHERE id=? AND owner=? AND state='running' AND lease_until>?",
            (job["id"], job["owner"], now),
        ).rowcount
        if not changed:
            db.rollback()
            raise RuntimeError("Lease lost before completion")
        db.execute(
            "UPDATE runs SET result=?,status='completed',updated=? WHERE id=?",
            (dumps(result), now, job["run_id"]),
        )
        if cacheable and settings().cache_enabled:
            key = db.execute("SELECT cache_key FROM runs WHERE id=?", (job["run_id"],)).fetchone()[0]
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES(?,?,?)",
                (key, dumps(result), now + settings().cache_ttl_s),
            )
        db.commit()


def heartbeat(owner, stage, started):
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO heartbeats VALUES(?,?,?,?)", (owner, stage, time.time(), started))


def add_feedback(run_id, value):
    with connection() as db:
        db.execute(
            "INSERT INTO feedback(run_id,satisfactory,reason,created) VALUES(?,?,?,?)",
            (run_id, int(value.satisfactory), value.reason, time.time()),
        )


def dashboard():
    with connection() as db:
        runs = [
            dict(r)
            for r in db.execute(
                "SELECT id,status,created,updated,cached,prompt_version,correlation_id FROM runs ORDER BY created DESC LIMIT 100"
            )
        ]
        counts = {r[0]: r[1] for r in db.execute("SELECT status,count(*) FROM runs GROUP BY status")}
        workers = [dict(r) for r in db.execute("SELECT * FROM heartbeats")]
        feedback = db.execute("SELECT count(*),avg(satisfactory) FROM feedback").fetchone()
        quarantine_count = db.execute("SELECT count(*) FROM quarantine").fetchone()[0]
        quality = [
            {"run_id": r["run_id"], "created": r["created"], **json.loads(r["scores"])}
            for r in db.execute("SELECT * FROM quality ORDER BY created DESC LIMIT 40")
        ]
        step_rows = db.execute("SELECT agent,kind,data FROM events").fetchall()
    agents = {}
    for row in step_rows:
        agent = agents.setdefault(
            row["agent"],
            {
                "steps": 0,
                "tool_calls": 0,
                "latencies_s": [],
                "retries": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost": 0,
                "tasks": 0,
                "successes": 0,
                "model_attempts": 0,
            },
        )
        data = json.loads(row["data"])
        if row["kind"] == "step":
            agent["steps"] += 1
            agent["latencies_s"].append(data.get("latency_s", 0))
        if row["kind"] == "tool":
            agent["tool_calls"] += 1
        if row["kind"] == "model":
            agent["model_attempts"] += 1
            for k in ["prompt_tokens", "completion_tokens", "cost"]:
                agent[k] += data.get(k) or 0
        if row["kind"] == "provider_failure":
            agent["model_attempts"] += 1
        if row["kind"] == "provider_retry":
            agent["retries"] += 1
        if row["kind"] == "task_completed":
            agent["tasks"] += 1
            agent["successes"] += int(data.get("success", False))
    for a in agents.values():
        a["retry_rate"] = a["retries"] / a["model_attempts"] if a["model_attempts"] else 0
        a["success_rate"] = a["successes"] / a["tasks"] if a["tasks"] else None
        a["steps_per_run"] = a["steps"] / a["tasks"] if a["tasks"] else None
        a["tool_calls_per_run"] = a["tool_calls"] / a["tasks"] if a["tasks"] else None
    return {
        "runs": runs,
        "counts": counts,
        "workers": workers,
        "feedback": {"count": feedback[0], "satisfaction_rate": feedback[1]},
        "quarantine_count": quarantine_count,
        "agents": agents,
        "quality": quality,
    }
