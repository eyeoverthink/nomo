"""Talk to a local Ollama daemon.

Cloud stubs are never selected. Set OLLAMA_HOST if the daemon is not on
127.0.0.1:11434.
"""

import json
import time
import urllib.error
import urllib.request

from nomo import select
from nomo.paths import EMBED_MODEL, OLLAMA, REASON_MODEL, ROUTE_MODEL

_CACHE = {"at": 0.0, "models": []}


class OllamaError(RuntimeError):
    pass


def _post(path, payload, timeout):
    request = urllib.request.Request(
        OLLAMA.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError("Ollama is not reachable at %s (%s). Run: python nomo.py setup" % (OLLAMA, exc.reason)) from exc
    except TimeoutError as exc:
        raise OllamaError("Ollama timed out on %s" % path) from exc


def inventory(refresh=False):
    now = time.time()
    if not refresh and _CACHE["models"] and now - _CACHE["at"] < 5:
        return list(_CACHE["models"])
    request = urllib.request.Request(OLLAMA.rstrip("/") + "/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError("Ollama is not reachable at %s (%s). Run: python nomo.py setup" % (OLLAMA, exc.reason)) from exc
    models = []
    for item in data.get("models") or []:
        name = item.get("name")
        if not name:
            continue
        models.append(
            {
                "name": name,
                "size": int(item.get("size") or 0),
                "remote_host": item.get("remote_host") or "",
            }
        )
    _CACHE["at"] = now
    _CACHE["models"] = models
    return list(models)


def route_model():
    return select.choose(inventory(), ROUTE_MODEL, select.PUBLIC_ROUTE, "route")


def reason_model():
    return select.choose(inventory(), REASON_MODEL, select.PUBLIC_REASON, "reason")


def embed_model():
    return select.choose(inventory(), EMBED_MODEL, select.PUBLIC_EMBED, "embed")


def chat(model, messages, timeout=180, temperature=0.4, num_predict=700):
    if not model:
        raise OllamaError("No local chat model is selected. Run: python nomo.py setup")
    data = _post(
        "/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        },
        timeout=timeout,
    )
    message = data.get("message") or {}
    return (message.get("content") or "").strip()


def embed(text):
    model = embed_model()
    if not model:
        return []
    data = _post("/api/embeddings", {"model": model, "prompt": text[:2000]}, timeout=60)
    vector = data.get("embedding") or []
    return vector if isinstance(vector, list) else []
