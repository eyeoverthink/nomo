"""JEV: a local Journaled Event Vault.

This is a hash-chained log on disk. It is not TypeSafe Jev and it does not
call jev-1.14.0. The shape is a typed event with a previous hash, so a later
reader can see whether the file was edited in the middle.
"""

import hashlib
import json
import os
import time
import uuid

from nomo.paths import JOURNAL


def _path():
    os.makedirs(JOURNAL, exist_ok=True)
    return os.path.join(JOURNAL, "events.jsonl")


def _last_hash():
    path = _path()
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return "0" * 64
    last = ""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    try:
        return json.loads(last).get("hash") or ("0" * 64)
    except json.JSONDecodeError:
        return "0" * 64


def append(kind, summary, data=None, actor="nomo"):
    prev = _last_hash()
    event = {
        "id": "jev-" + uuid.uuid4().hex[:12],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "actor": actor,
        "kind": kind,
        "summary": summary[:500],
        "data": data or {},
        "prev": prev,
    }
    raw = json.dumps(event, sort_keys=True, ensure_ascii=False)
    event["hash"] = hashlib.sha256((prev + raw).encode("utf-8")).hexdigest()
    with open(_path(), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    try:
        from nomo import record

        record.seal(kind, summary, data, actor)
    except Exception:
        pass
    return event


def recent(n=8):
    path = _path()
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows[-n:]


def verify():
    path = _path()
    if not os.path.exists(path):
        return {"ok": True, "count": 0, "broken_at": ""}
    prev = "0" * 64
    count = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            event = json.loads(line)
            stated_prev = event.get("prev")
            stated_hash = event.get("hash")
            check = dict(event)
            check.pop("hash", None)
            raw = json.dumps(check, sort_keys=True, ensure_ascii=False)
            digest = hashlib.sha256((stated_prev + raw).encode("utf-8")).hexdigest()
            if stated_prev != prev or digest != stated_hash:
                return {"ok": False, "count": count, "broken_at": event.get("id", "")}
            prev = stated_hash
    return {"ok": True, "count": count, "broken_at": ""}
