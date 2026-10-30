"""Honcho-style peer cards.

A peer is a markdown file of conclusions, each with a confidence and the
journal id that supports it. Confidence here is a weight the operator or a
dream pass wrote down. It is a note, not a calibrated probability.
"""

import os
import re

from nomo.paths import PEERS
from nomo import vault


def operator_id():
    name = os.environ.get("NOMO_OPERATOR", "").strip()
    if not name:
        return "operator", "Operator"
    slug = re.sub(r"[^a-z0-9_-]", "", name.lower()) or "operator"
    return slug, name


def _file(peer):
    safe = re.sub(r"[^a-z0-9_-]", "", str(peer).lower()) or "unknown"
    return "peers/" + safe + ".md"


def ensure_defaults():
    vault.ensure()
    os.makedirs(PEERS, exist_ok=True)
    slug, title = operator_id()
    cards = ((slug, title), ("self", "NoMo"))
    for name, label in cards:
        path = _file(name)
        if not vault.read(path):
            vault.write(path, "# %s\n\n## Conclusions\n\n## Open questions\n\n" % label)


def note(peer, conclusion, confidence=0.5, evidence=""):
    ensure_defaults()
    path = _file(peer)
    body = vault.read(path)
    if "## Conclusions" not in body:
        body += "\n## Conclusions\n"
    line = "- [%.2f] %s" % (max(0.0, min(1.0, float(confidence))), conclusion.strip())
    if evidence:
        line += " evidence: %s" % evidence
    parts = body.split("## Open questions", 1)
    head = parts[0].rstrip() + "\n" + line + "\n\n"
    if len(parts) == 2:
        body = head + "## Open questions" + parts[1]
    else:
        body = head + "## Open questions\n"
    vault.write(path, body)
    return path


def read(peer):
    ensure_defaults()
    return vault.read(_file(peer))


def context_block():
    ensure_defaults()
    slug, _title = operator_id()
    chunks = []
    for name in ("self", slug):
        text = read(name).strip()
        if text:
            chunks.append(text[:1200])
    return "\n\n".join(chunks)
