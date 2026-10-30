"""Tools the local agent is allowed to run.

Shell, git push, replication, and the dream cycle are operator commands.
A model reply cannot copy the agent or rewrite its own code.
"""

import os
import sys

from nomo import absorb, doctor, graph, honcho, ledger, ollama_client, record, vault
from nomo import __version__
from nomo.paths import ROOT, SKILLS, VAULT


def _needle_state():
    try:
        import needle  # noqa: F401
        return "importable"
    except ImportError:
        pass
    python = doctor.venv_python()
    if not python:
        return "not-installed"
    venv = os.path.dirname(os.path.dirname(python))
    candidates = [os.path.join(venv, "Lib", "site-packages", "needle", "__init__.py")]
    lib = os.path.join(venv, "lib")
    if os.path.isdir(lib):
        for name in os.listdir(lib):
            candidates.append(os.path.join(lib, name, "site-packages", "needle", "__init__.py"))
    if any(os.path.isfile(path) for path in candidates):
        if os.path.normcase(sys.executable) != os.path.normcase(python):
            return "installed-in-.venv"
        return "importable"
    return "not-installed"


def skills():
    vault.ensure()
    if not os.path.isdir(SKILLS):
        return []
    return sorted(name for name in os.listdir(SKILLS) if name.endswith(".md"))


def status():
    route = ""
    reason = ""
    embed = ""
    code = ""
    ollama = ""
    local_count = 0
    skipped_count = 0
    try:
        models = ollama_client.inventory()
        from nomo import select

        route = ollama_client.route_model()
        reason = ollama_client.reason_model()
        embed = ollama_client.embed_model()
        code = ollama_client.code_model()
        ollama = "up"
        local_count = sum(1 for item in models if select.is_auto(item))
        skipped_count = len(models) - local_count
    except ollama_client.OllamaError as exc:
        ollama = str(exc)
    chain = ledger.verify()
    slug, _title = honcho.operator_id()
    return {
        "version": __version__,
        "ollama": ollama,
        "route_model": route,
        "reason_model": reason,
        "embed_model": embed or "none",
        "code_model": code or "none",
        "needle3": _needle_state(),
        "operator": slug,
        "root": ROOT,
        "vault": VAULT,
        "skills": skills(),
        "local_models": local_count,
        "skipped_models": skipped_count,
        "journal_ok": chain["ok"],
        "journal_events": chain["count"],
        "record_ok": record.verify()["ok"],
        "record_events": record.verify()["count"],
        "graph_rows": graph.count(),
    }


def list_files(folder=""):
    vault.ensure()
    base = os.path.abspath(os.path.join(ROOT, folder))
    root = os.path.normcase(os.path.abspath(ROOT))
    base_n = os.path.normcase(base)
    if base_n != root and not base_n.startswith(root + os.sep):
        raise ValueError("That folder leaves the agent directory.")
    if not os.path.isdir(base):
        return []
    names = []
    for name in sorted(os.listdir(base)):
        if name in {".venv", ".git", "children"} or name.startswith("."):
            continue
        names.append(name + ("/" if os.path.isdir(os.path.join(base, name)) else ""))
    return names[:80]


def read_file(path):
    full = os.path.abspath(os.path.join(ROOT, path))
    root = os.path.normcase(os.path.abspath(ROOT))
    full_n = os.path.normcase(full)
    if full_n != root and not full_n.startswith(root + os.sep):
        raise ValueError("That file leaves the agent directory.")
    if not os.path.isfile(full):
        return ""
    if os.path.getsize(full) > 200_000:
        return "File is larger than 200000 bytes. Read a note in the vault instead."
    with open(full, encoding="utf-8", errors="replace") as handle:
        return handle.read()


TOOLS = {
    "status": lambda **_: status(),
    "vault_search": lambda q, **_: vault.search(q),
    "vault_read": lambda name, **_: vault.read(name),
    "vault_write": lambda name, body, **_: vault.write(name, body),
    "peer_note": lambda peer, conclusion, confidence=0.5, evidence="", **_: honcho.note(
        peer, conclusion, confidence, evidence
    ),
    "peer_read": lambda peer="", **_: honcho.read(peer or honcho.operator_id()[0]),
    "ledger_recent": lambda n=8, **_: ledger.recent(int(n)),
    "list_files": lambda folder="", **_: list_files(folder),
    "read_file": lambda path, **_: read_file(path),
    "graph_note": lambda name, body, kind="decision", evidence="", **_: graph.remember(name, body, kind, evidence),
    "graph_lookup": lambda q, **_: graph.lookup(q),
    "absorb": lambda url, **_: absorb.fetch(url),
}


def run(name, args):
    if name not in TOOLS:
        raise KeyError(name)
    if not isinstance(args, dict):
        raise ValueError("Tool args must be an object.")
    result = TOOLS[name](**args)
    ledger.append("tool", name, {"args": args, "ok": True})
    return result
