"""Structured memory in a local SQLite file.

Rows are entities, decisions, and modules. The file is vault/graph.sqlite.
Neo4j is not required.
"""

import os
import re
import sqlite3
import time

from nomo.paths import GRAPH

_KINDS = {"entity", "decision", "module"}


def _connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nodes ("
        "id INTEGER PRIMARY KEY, ts TEXT, kind TEXT, name TEXT, body TEXT, evidence TEXT)"
    )
    return conn


def remember(name, body, kind="decision", evidence="", path=None):
    kind = kind if kind in _KINDS else "decision"
    target = path or GRAPH
    conn = _connect(target)
    try:
        conn.execute(
            "INSERT INTO nodes (ts, kind, name, body, evidence) VALUES (?, ?, ?, ?, ?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), kind, name.strip()[:120], body.strip()[:2000], evidence[:80]),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def lookup(query, limit=6, path=None):
    target = path or GRAPH
    if not os.path.exists(target):
        return []
    words = [word for word in re.findall(r"[a-z0-9]{3,}", query.lower())][:8]
    conn = _connect(target)
    try:
        if not words:
            rows = conn.execute(
                "SELECT kind, name, body, evidence FROM nodes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            clause = " OR ".join(["lower(name) LIKE ? OR lower(body) LIKE ?"] * len(words))
            args = []
            for word in words:
                args.extend(["%" + word + "%", "%" + word + "%"])
            args.append(limit)
            rows = conn.execute(
                "SELECT kind, name, body, evidence FROM nodes WHERE %s ORDER BY id DESC LIMIT ?" % clause,
                args,
            ).fetchall()
        return [
            {"kind": kind, "name": name, "body": body, "evidence": evidence}
            for kind, name, body, evidence in rows
        ]
    finally:
        conn.close()


def count(path=None):
    target = path or GRAPH
    if not os.path.exists(target):
        return 0
    conn = _connect(target)
    try:
        return conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    finally:
        conn.close()
