"""Context packed for every prompt from the three local stores.

Episodic lines come from the sealed record. Semantic hits come from the
vault embedding index, then from keyword overlap. Graph rows come from
SQLite. Fossils are verified patterns saved by the evolve command.
"""

import os

from nomo import graph, record, vault
from nomo.paths import FOSSILS


def _fossils(limit=2):
    if not os.path.isdir(FOSSILS):
        return []
    paths = []
    for name in os.listdir(FOSSILS):
        if name.endswith(".md"):
            full = os.path.join(FOSSILS, name)
            paths.append((os.path.getmtime(full), name))
    paths.sort()
    chunks = []
    for _mtime, name in paths[-limit:]:
        text = vault.read("fossils/" + name)
        if text:
            chunks.append(text[:800])
    return chunks


def pack(query, limit=3):
    parts = []
    episodes = record.recent(4)
    if episodes:
        lines = ["%s %s" % (row.get("kind"), row.get("summary")) for row in episodes]
        parts.append("EPISODIC\n" + "\n".join(lines)[:800])
    try:
        hits = vault.search(query or "", limit=limit)
    except Exception:
        hits = []
    if hits:
        lines = ["%s %s" % (hit.get("name"), hit.get("preview")) for hit in hits[:limit]]
        parts.append("SEMANTIC\n" + "\n".join(lines)[:700])
    rows = graph.lookup(query or "", limit=4)
    if rows:
        lines = ["%s %s: %s" % (row["kind"], row["name"], row["body"][:180]) for row in rows]
        parts.append("GRAPH\n" + "\n".join(lines)[:600])
    fossils = _fossils()
    if fossils:
        parts.append("FOSSILS\n" + "\n\n".join(fossils)[:800])
    return "\n\n".join(parts)
