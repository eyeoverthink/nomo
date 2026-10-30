"""Obsidian-style markdown vault. Wikilinks are filenames."""

import getpass
import json
import os
import re
import shutil

from nomo import ollama_client
from nomo.paths import NOTES, SEED, SKILLS, VAULT

_OPERATOR_MARK = "<!-- operator:unset -->"


def _copy_missing(src, dst):
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            _copy_missing(os.path.join(src, name), os.path.join(dst, name))
        return
    if os.path.exists(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def _personalize_user():
    path = os.path.join(VAULT, "USER.md")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if _OPERATOR_MARK not in text:
        return
    account = os.environ.get("NOMO_OPERATOR", "").strip() or getpass.getuser()
    account = account.replace("\n", " ").replace("\r", " ")
    text = text.replace(_OPERATOR_MARK, "Local account: %s" % account)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure():
    os.makedirs(NOTES, exist_ok=True)
    os.makedirs(SKILLS, exist_ok=True)
    os.makedirs(os.path.join(VAULT, "dreams"), exist_ok=True)
    os.makedirs(os.path.join(VAULT, "peers"), exist_ok=True)
    os.makedirs(os.path.join(VAULT, "journal"), exist_ok=True)
    if os.path.isdir(SEED):
        _copy_missing(SEED, VAULT)
    elif not os.path.isfile(os.path.join(VAULT, "HOME.md")):
        with open(os.path.join(VAULT, "HOME.md"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("# NoMo\n\nThis vault is the memory.\n")
    _personalize_user()


def _safe_name(name):
    cleaned = name.replace("\\", "/").strip().lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise ValueError("That note name leaves the vault.")
    if not cleaned.endswith(".md"):
        cleaned += ".md"
    root = os.path.normcase(os.path.abspath(VAULT))
    full = os.path.normcase(os.path.abspath(os.path.join(VAULT, cleaned)))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("That note name leaves the vault.")
    return full, cleaned


def write(name, body):
    ensure()
    full, cleaned = _safe_name(name)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    _index_one(cleaned, body)
    return cleaned


def read(name):
    ensure()
    full, _cleaned = _safe_name(name)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8") as handle:
        return handle.read()


def list_notes():
    ensure()
    found = []
    for dirpath, _, files in os.walk(VAULT):
        for name in files:
            if name.endswith(".md"):
                rel = os.path.relpath(os.path.join(dirpath, name), VAULT).replace("\\", "/")
                found.append(rel)
    return sorted(found)


def _tokens(text):
    return re.findall(r"[a-z0-9']{3,}", text.lower())


def keyword_search(query, limit=8):
    words = set(_tokens(query))
    scored = []
    for name in list_notes():
        body = read(name)
        hay = set(_tokens(name + "\n" + body))
        score = len(words & hay)
        if score:
            scored.append((score, name, body[:240].replace("\n", " ")))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [{"name": name, "score": score, "preview": preview} for score, name, preview in scored[:limit]]


def _index_path():
    return os.path.join(VAULT, ".index.json")


def _index_one(name, body):
    try:
        vector = ollama_client.embed(name + "\n" + body[:1500])
    except ollama_client.OllamaError:
        return
    if not vector:
        return
    path = _index_path()
    index = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                index = json.load(handle)
        except json.JSONDecodeError:
            index = {}
    index[name] = vector
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(index, handle)


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def search(query, limit=6):
    lexical = keyword_search(query, limit=limit)
    try:
        vector = ollama_client.embed(query)
    except ollama_client.OllamaError:
        return lexical
    path = _index_path()
    if not vector or not os.path.exists(path):
        return lexical
    try:
        with open(path, encoding="utf-8") as handle:
            index = json.load(handle)
    except json.JSONDecodeError:
        return lexical
    ranked = []
    for name, stored in index.items():
        ranked.append((_cosine(vector, stored), name))
    ranked.sort(reverse=True)
    semantic = []
    for score, name in ranked[:limit]:
        if score < 0.25:
            continue
        body = read(name)
        semantic.append({"name": name, "score": round(score, 3), "preview": body[:240].replace("\n", " ")})
    if not semantic:
        return lexical
    return semantic
