"""Architect, critic, and executor.

The architect writes one Python file. The critic reads it. The executor
runs it only when NOMO_ALLOW_RUN=1, and only inside vault/sandbox.
A passing run is saved as a fossil the next prompt can read.
The cycle does not edit nomo/*.py and does not commit or push git.
"""

import os
import re
import subprocess
import sys
import time

from nomo import graph, ledger, ollama_client, vault
from nomo.paths import FOSSILS, SANDBOX

_BANNED = (
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "ctypes",
    "os.system",
    "shutil",
    "eval(",
    "exec(",
    "__import__",
    "pickle",
    "ghidra",
    "radare",
)


def blocked(source):
    low = source.lower()
    for item in _BANNED:
        if item in low:
            return item
    return ""


def extract_code(text):
    if "```" not in text:
        return text.strip()
    parts = text.split("```")
    for block in parts[1::2]:
        lines = block.splitlines()
        if lines and lines[0].strip().lower() in {"python", "py"}:
            return "\n".join(lines[1:]).strip()
        return block.strip()
    return text.strip()


def _ask(model, system, user, predict=700):
    return ollama_client.chat(
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=180,
        temperature=0.2,
        num_predict=predict,
    )


def _run(source, job):
    if os.environ.get("NOMO_ALLOW_RUN", "") != "1":
        return {"ran": False, "code": None, "stdout": "", "stderr": "Set NOMO_ALLOW_RUN=1 to execute."}
    hit = blocked(source)
    if hit:
        return {"ran": False, "code": None, "stdout": "", "stderr": "Blocked source: " + hit}
    folder = os.path.join(SANDBOX, job)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "main.py")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(source)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "PYTHONIOENCODING": "utf-8",
    }
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ran": True, "code": 124, "stdout": "", "stderr": "timed out"}
    return {
        "ran": True,
        "code": proc.returncode,
        "stdout": (proc.stdout or "")[:4000],
        "stderr": (proc.stderr or "")[:4000],
    }


def _fossil(task, source, result):
    os.makedirs(FOSSILS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    body = "# Fossil %s\n\nTask: %s\n\n```python\n%s\n```\n" % (stamp, task[:300], source)
    name = vault.write("fossils/%s.md" % stamp, body)
    graph.remember(task[:80], "Verified local Python. Exit %s." % result.get("code"), "module", name)
    return name


def run(task, rounds=2):
    task = task.strip()
    if not task:
        raise ValueError("Give the evolve command a task.")
    rounds = max(1, min(int(rounds), 3))
    model = ollama_client.code_model()
    critique = ""
    output = ""
    last_code = ""
    result = {"ran": False, "code": None, "stdout": "", "stderr": ""}
    fossil = ""
    for index in range(rounds):
        code_text = _ask(
            model,
            "Write one Python file. Use the standard library only. "
            "Include asserts that check the task. Reply with one python code fence and nothing else.",
            "Task:\n%s\n\nCritic:\n%s\n\nExecutor:\n%s" % (task, critique[:800], output[:800]),
            predict=800,
        )
        last_code = extract_code(code_text)
        critique = _ask(
            model,
            "Read the Python. Name one concrete defect, or reply OK when the asserts match the task.",
            last_code[:4000],
            predict=250,
        )
        result = _run(last_code, "r%d" % index)
        output = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
        if result.get("ran") and result.get("code") == 0 and not blocked(last_code):
            fossil = _fossil(task, last_code, result)
            break
    event = ledger.append(
        "evolve",
        task[:180],
        {"code": result.get("code"), "fossil": fossil, "model": model},
    )
    return {
        "model": model,
        "rounds": rounds,
        "code": result.get("code"),
        "ran": result.get("ran"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "fossil": fossil,
        "event": event["id"],
    }
