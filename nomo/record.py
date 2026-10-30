"""Episodic log. Every sealed line is SHA-256 chained to the line before it.

The chain is the DOC-SEAL for this process. It lives at vault/record.jsonl.
Editing a middle line breaks the next check.
"""

import hashlib
import json
import os
import time
import uuid

from nomo.paths import RECORD


def _last(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return "0" * 64
    last = ""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    try:
        return json.loads(last).get("seal") or ("0" * 64)
    except json.JSONDecodeError:
        return "0" * 64


def seal(kind, summary, data=None, actor="nomo", path=None):
    target = path or RECORD
    os.makedirs(os.path.dirname(target), exist_ok=True)
    prev = _last(target)
    event = {
        "id": "rec-" + uuid.uuid4().hex[:12],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "actor": actor,
        "kind": kind,
        "summary": (summary or "")[:500],
        "data": data or {},
        "prev": prev,
    }
    raw = json.dumps(event, sort_keys=True, ensure_ascii=False)
    event["seal"] = hashlib.sha256((prev + raw).encode("utf-8")).hexdigest()
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def recent(n=6, path=None):
    target = path or RECORD
    if not os.path.exists(target):
        return []
    rows = []
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows[-n:]


def verify(path=None):
    target = path or RECORD
    if not os.path.exists(target):
        return {"ok": True, "count": 0, "broken_at": ""}
    prev = "0" * 64
    count = 0
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            event = json.loads(line)
            stated = event.get("seal")
            check = dict(event)
            check.pop("seal", None)
            raw = json.dumps(check, sort_keys=True, ensure_ascii=False)
            digest = hashlib.sha256((event.get("prev", "") + raw).encode("utf-8")).hexdigest()
            if event.get("prev") != prev or digest != stated:
                return {"ok": False, "count": count, "broken_at": event.get("id", "")}
            prev = stated
    return {"ok": True, "count": count, "broken_at": ""}
