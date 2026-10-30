"""Local replication.

Copies this agent into children/<name> with a new empty vault and a parent
pointer. It does not start the child, does not schedule it, and does not copy
the journal.
"""

import os
import shutil

from nomo import ledger
from nomo.paths import CHILDREN, ROOT

SKIP = {".venv", ".git", "children", "vault", "__pycache__", ".env"}


def run(name):
    cleaned = "".join(ch for ch in name.lower() if ch.isalnum() or ch in "-")
    if not cleaned or cleaned in {"nomo", "nomo-local"}:
        raise ValueError("Pick a short child name, letters and dashes.")
    os.makedirs(CHILDREN, exist_ok=True)
    dest = os.path.join(CHILDREN, cleaned)
    if os.path.exists(dest):
        raise ValueError("A child with that name already exists.")
    os.makedirs(dest)
    for entry in os.listdir(ROOT):
        if entry in SKIP or entry.startswith("."):
            continue
        src = os.path.join(ROOT, entry)
        target = os.path.join(dest, entry)
        if os.path.isdir(src):
            shutil.copytree(
                src,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(src, target)
    pointer = os.path.join(dest, "PARENT.txt")
    with open(pointer, "w", encoding="utf-8") as handle:
        handle.write("parent: %s\nname: %s\n" % (ROOT, cleaned))
    event = ledger.append("replicate", "child " + cleaned, {"path": dest})
    return {"path": dest, "event": event["id"]}
