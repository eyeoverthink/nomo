"""One turn.

Needle 3 routes a tool when it imports. Otherwise the route model does.
The reason model writes the reply from measured tool output. A turn may use
at most three tools. The process exits when the command exits.
"""

import json
import os

from nomo import honcho, ledger, ollama_client, tools, vault


def system_prompt(model):
    return (
        "You are NoMo, a local file-backed agent. "
        "You are running %s. Claim this model only. "
        "If a note or an older journal line names a different model, the running model is still %s. "
        "Memory is the vault and the journal on the machine that started this process. "
        "Say [measured] when a fact came from a tool result or a file in this prompt. "
        "Say [recall] for anything else. "
        "If the prompt does not contain the fact, say you do not know. "
        "Do not invent weather, hashes, paths, or a person's name. "
        "Do not propose a git push, a new privilege, or a shell command."
        % ((model or "no model"), (model or "no model"))
    )


def _extract_call(text):
    start = text.find("{")
    while start >= 0:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : index + 1]
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "tool" in obj:
                        return obj
                    break
        start = text.find("{", start + 1)
    return None


def _needle_call(user_text):
    os.environ.setdefault("NEEDLE_TELEMETRY", "0")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    try:
        import needle
    except ImportError:
        return None
    specs = []
    for name in tools.TOOLS:
        specs.append(
            {
                "name": name,
                "description": "Local NoMo tool %s. Use only the arguments that tool needs." % name,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "q": {"type": "string"},
                        "name": {"type": "string"},
                        "body": {"type": "string"},
                        "peer": {"type": "string"},
                        "conclusion": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence": {"type": "string"},
                        "path": {"type": "string"},
                        "folder": {"type": "string"},
                        "n": {"type": "integer"},
                    },
                },
            }
        )
    try:
        agent = needle.Needle(tools=specs, system="Route one local NoMo tool or none.", generation=3)
        if hasattr(agent, "complete"):
            return agent.complete(user_text)
        return agent.run(user_text)
    except Exception as exc:
        return {"error": str(exc)[:300]}


def _as_args(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _context():
    vault.ensure()
    honcho.ensure_defaults()
    parts = [
        "SELF\n" + vault.read("SELF.md")[:1200],
        "USER\n" + vault.read("USER.md")[:600],
        "PEERS\n" + honcho.context_block(),
        "PROPOSALS\n" + vault.read("dreams/PROPOSALS.md")[-600:],
        "RECENT\n" + json.dumps(ledger.recent(4), ensure_ascii=False)[:1200],
    ]
    return "\n\n".join(parts)


def _route_tool(user_text, route):
    if not route:
        return None
    raw = ollama_client.chat(
        route,
        [
            {
                "role": "system",
                "content": "You only route tools. Reply NONE if no tool is needed. "
                "Otherwise reply with one JSON object {\"tool\":\"name\",\"args\":{}} and nothing else. "
                "Tools: status, vault_search, vault_read, vault_write, peer_note, peer_read, ledger_recent, list_files, read_file.",
            },
            {"role": "user", "content": user_text},
        ],
        timeout=90,
        temperature=0.0,
        num_predict=180,
    )
    if raw.strip().upper().startswith("NONE"):
        return None
    return _extract_call(raw)


def ask(user_text, rounds=3):
    vault.ensure()
    route = ollama_client.route_model()
    reason = ollama_client.reason_model()
    ledger.append("ask", user_text[:240], {"route": route, "reason": reason})
    observations = []
    needle_meta = _needle_call(user_text)
    calls = []
    if isinstance(needle_meta, dict):
        calls = needle_meta.get("function_calls") or []
    used_needle = bool(calls)
    if used_needle:
        for call in calls[:rounds]:
            name = call.get("name")
            args = _as_args(call.get("arguments") if "arguments" in call else call.get("args"))
            try:
                result = tools.run(name, args)
                observations.append({"tool": name, "result": result, "via": "needle3"})
            except Exception as exc:
                observations.append({"tool": name, "error": str(exc)[:300], "via": "needle3"})
    else:
        for _ in range(rounds):
            follow = user_text
            if observations:
                follow = user_text + "\nAlready ran: " + json.dumps(observations, default=str)[:2000]
            call = _route_tool(follow, route)
            if not call:
                break
            name = str(call.get("tool") or "")
            args = _as_args(call.get("args"))
            try:
                result = tools.run(name, args)
                observations.append({"tool": name, "result": result, "via": route})
            except Exception as exc:
                observations.append({"tool": name, "error": str(exc)[:300], "via": route})
                break
    model = reason or route
    reply = ollama_client.chat(
        model,
        [
            {"role": "system", "content": system_prompt(model)},
            {
                "role": "user",
                "content": _context()
                + "\n\nOPERATOR\n"
                + user_text
                + "\n\nMEASURED\n"
                + json.dumps(observations, default=str)[:8000]
                + "\n\nAnswer in one short paragraph.",
            },
        ],
        timeout=180,
        temperature=0.2,
    )
    ledger.append("reply", reply[:240], {"tools": [item.get("tool") for item in observations]})
    return {"reply": reply, "model": model, "tools": observations, "needle": used_needle}


def parallel(goal):
    """Three short passes on the route model, then one merge on the reason model."""
    route = ollama_client.route_model()
    reason = ollama_client.reason_model()
    roles = {
        "scout": "List the concrete facts the operator would need. Stay with the files and the goal.",
        "critic": "Name the weakest assumption in the goal and what would falsify it.",
        "builder": "Name the smallest file or command that would move the goal forward. Use the existing NoMo commands.",
    }
    from concurrent.futures import ThreadPoolExecutor

    def one(role, instruction):
        text = ollama_client.chat(
            route or reason,
            [
                {"role": "system", "content": instruction + " Running model: " + (route or reason or "no model")},
                {"role": "user", "content": goal},
            ],
            timeout=180,
            num_predict=350,
        )
        return role, text

    parts = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one, role, instruction) for role, instruction in roles.items()]
        for future in futures:
            role, text = future.result()
            parts[role] = text
    merged = ollama_client.chat(
        reason or route,
        [
            {
                "role": "system",
                "content": "Merge the three notes into one short plan. Mark disagreements. Keep a step only when one of the notes wrote it.",
            },
            {"role": "user", "content": json.dumps(parts, ensure_ascii=False)[:8000]},
        ],
        timeout=180,
    )
    ledger.append("parallel", goal[:200], {"roles": list(parts)})
    return {"roles": parts, "plan": merged, "route": route, "reason": reason}


def choose(question, options):
    """Local typed choice. The score is uncalibrated. Hosted Jev is not called."""
    model = ollama_client.route_model() or ollama_client.reason_model()
    raw = ollama_client.chat(
        model,
        [
            {
                "role": "system",
                "content": "Reply with JSON only: {\"choice\":\"\",\"score\":0.0,\"because\":\"\"}. "
                "choice must be one of the options. score is an uncalibrated confidence from 0 to 1.",
            },
            {"role": "user", "content": question + "\noptions: " + json.dumps(options)},
        ],
        timeout=120,
        temperature=0.1,
        num_predict=200,
    )
    parsed = _extract_choice(raw, options)
    parsed["model"] = model
    parsed["method"] = "local-choice"
    parsed["calibrated"] = False
    ledger.append("choice", parsed.get("choice") or "unparsed", {"question": question[:180]})
    return parsed


def _extract_choice(raw, options):
    start = raw.find("{")
    if start >= 0:
        end = raw.rfind("}")
        if end > start:
            try:
                obj = json.loads(raw[start : end + 1])
                choice = str(obj.get("choice") or "")
                if choice not in options:
                    choice = ""
                score = obj.get("score", 0)
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = 0.0
                return {
                    "choice": choice,
                    "score": max(0.0, min(1.0, score)),
                    "because": str(obj.get("because") or "")[:400],
                    "raw": raw[:500],
                }
            except json.JSONDecodeError:
                pass
    return {"choice": "", "score": 0.0, "because": "The model did not return a choice.", "raw": raw[:500]}
