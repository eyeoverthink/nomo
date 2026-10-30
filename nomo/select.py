"""Choose a local Ollama tag.

Public tags win. A cloud stub, a tiny remote placeholder, or a 70B/120B tag
is skipped unless the operator pinned a real local file with an env variable.
Any other local model still runs when the public tags are absent.
"""

PUBLIC_ROUTE = (
    "llama3.2:latest",
    "llama3.2:3b",
    "llama3.2",
    "llama3.2:1b",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "phi3:mini",
    "gemma2:2b",
)
PUBLIC_REASON = (
    "llama3.1:8b",
    "llama3:latest",
    "llama3:8b",
    "llama3.1:latest",
    "mistral:latest",
    "qwen2.5:7b",
    "gemma2:9b",
    "hermes3:latest",
)
PUBLIC_EMBED = (
    "nomic-embed-text:latest",
    "nomic-embed-text",
    "mxbai-embed-large:latest",
    "all-minilm:latest",
)
PUBLIC_CODE = (
    "qwen2.5-coder:7b",
    "qwen2.5-coder:latest",
    "qwen2.5-coder:3b",
    "deepseek-coder-v2:16b",
    "deepseek-coder:6.7b",
    "llama3.3:latest",
    "llama3.1:8b",
    "llama3:latest",
)

MIN_LOCAL_BYTES = 1_000_000
_HEAVY = ("70b", "72b", "120b", "405b")


def _heavy(name):
    low = name.lower()
    tag = low.split(":")[-1] if ":" in low else ""
    if tag in _HEAVY:
        return True
    return any(piece in low for piece in (":70b", ":72b", ":120b", ":405b", "-70b", "-72b", "-120b"))


def is_local_file(model):
    """True when the tag is a weight on disk, including large local weights."""
    if model.get("remote_host"):
        return False
    if "cloud" in model.get("name", "").lower():
        return False
    return int(model.get("size") or 0) >= MIN_LOCAL_BYTES


def is_auto(model):
    """True when NoMo may select the tag without an explicit pin."""
    return is_local_file(model) and not _heavy(model.get("name", ""))


def _resolve(inventory, name):
    if not name:
        return None
    for item in inventory:
        if item.get("name") == name:
            return item
    if ":" in name:
        return None
    heavy = None
    for item in inventory:
        if str(item.get("name", "")).split(":")[0] != name:
            continue
        if is_auto(item):
            return item
        heavy = heavy or item
    return heavy


def _chats(inventory):
    found = []
    for item in inventory:
        if not is_auto(item):
            continue
        low = item["name"].lower()
        if "embed" in low or "minilm" in low:
            continue
        found.append(item)
    return found


def choose(inventory, preferred, fallbacks, kind):
    pinned = _resolve(inventory, preferred)
    if pinned is not None and is_local_file(pinned):
        if is_auto(pinned) or preferred:
            # An explicit pin may be a large local weight. A cloud stub never qualifies.
            return pinned["name"]
    for name in fallbacks:
        found = _resolve(inventory, name)
        if found is not None and is_auto(found):
            return found["name"]
    if kind == "embed":
        embeds = []
        for item in inventory:
            if not is_auto(item):
                continue
            low = item["name"].lower()
            if "embed" in low or "minilm" in low:
                embeds.append(item)
        if not embeds:
            return ""
        embeds.sort(key=lambda item: int(item.get("size") or 0))
        return embeds[0]["name"]
    chats = _chats(inventory)
    if not chats:
        return ""
    if kind == "route":
        chats.sort(key=lambda item: int(item.get("size") or 0))
        return chats[0]["name"]
    big = [item for item in chats if int(item.get("size") or 0) >= 3_000_000_000]
    pool = big or chats
    pool.sort(key=lambda item: int(item.get("size") or 0), reverse=True)
    return pool[0]["name"]
