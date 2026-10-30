"""Tell a fresh clone which public models are still missing."""

import os
import shutil
import subprocess
import sys

from nomo import ollama_client, select
from nomo.paths import ROOT

PULLS = (
    ("llama3.2", ("llama3.2:latest", "llama3.2", "llama3.2:3b", "llama3.2:1b")),
    ("llama3.1:8b", ("llama3.1:8b", "llama3:latest", "llama3:8b", "llama3.1:latest")),
    ("nomic-embed-text", ("nomic-embed-text:latest", "nomic-embed-text")),
)


def venv_python():
    candidates = (
        os.path.join(ROOT, ".venv", "Scripts", "python.exe"),
        os.path.join(ROOT, ".venv", "bin", "python"),
        os.path.join(ROOT, ".venv", "bin", "python3"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def missing(models):
    names = set()
    bases = set()
    for item in models:
        if not select.is_auto(item):
            continue
        name = item["name"]
        names.add(name)
        bases.add(name.split(":")[0])
    needed = []
    for pull, options in PULLS:
        found = False
        for opt in options:
            if opt in names or opt.split(":")[0] in bases:
                found = True
                break
        if not found:
            needed.append(pull)
    return needed


def report():
    try:
        models = ollama_client.inventory(refresh=True)
        error = ""
    except ollama_client.OllamaError as exc:
        models = []
        error = str(exc)
    local = [item["name"] for item in models if select.is_auto(item)]
    skipped = [item["name"] for item in models if not select.is_auto(item)]
    return {
        "ollama": "up" if not error else error,
        "ollama_on_path": bool(shutil.which("ollama")),
        "route_model": ollama_client.route_model() if not error else "",
        "reason_model": ollama_client.reason_model() if not error else "",
        "embed_model": ollama_client.embed_model() if not error else "",
        "local_count": len(local),
        "skipped_count": len(skipped),
        "pull": missing(models),
        "venv_python": venv_python(),
    }


def pull_missing():
    if not shutil.which("ollama"):
        raise ollama_client.OllamaError("Install Ollama and start it, then run python nomo.py setup --pull")
    needed = missing(ollama_client.inventory(refresh=True))
    results = []
    for name in needed:
        proc = subprocess.run(["ollama", "pull", name], check=False)
        results.append({"model": name, "code": proc.returncode})
    return {"pulled": results, "still_missing": missing(ollama_client.inventory(refresh=True))}


def install_needle():
    python = venv_python()
    if not python:
        proc = subprocess.run([sys.executable, "-m", "venv", os.path.join(ROOT, ".venv")], check=False)
        if proc.returncode != 0:
            return {"code": proc.returncode, "python": ""}
        python = venv_python()
    if not python:
        return {"code": 1, "python": ""}
    req = os.path.join(ROOT, "requirements.txt")
    proc = subprocess.run([python, "-m", "pip", "install", "-r", req], check=False)
    return {"code": proc.returncode, "python": python}
