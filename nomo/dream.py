"""Dream-RSI cycle for the local agent.

One cycle explores a small tree, replays the saved scores, and promotes
the exploration policy that wins. It writes the report into the vault.
It leaves nomo/*.py alone, opens no shell, and pushes no remote.
"""

import json
import os
import time

from nomo import dream_rsi, ledger, ollama_client, vault
from nomo.paths import DREAMS


def run(goal="", branches=2, refine=1, rounds=1):
    vault.ensure()
    os.makedirs(DREAMS, exist_ok=True)
    rounds = max(1, min(int(rounds), 3))
    branches = max(1, min(int(branches), 4))
    refine = max(0, min(int(refine), 2))
    goal = (goal or _default_goal()).strip()
    model = ollama_client.reason_model() or ollama_client.route_model()
    worlds = os.path.join(DREAMS, "worlds")
    policy_path = os.path.join(DREAMS, "policy.json")
    last = None
    for _ in range(rounds):
        incumbent = dream_rsi.load_policy(policy_path)
        trace = _explore(goal, branches, refine, model)
        index = _next_index(worlds)
        folder = os.path.join(worlds, "iter%03d" % index)
        dream_rsi.write_trace(folder, trace)
        pool = dream_rsi.list_traces(worlds)
        choice = dream_rsi.select_policy(pool, incumbent)
        dream_rsi.save_policy(policy_path, choice["promoted"], _plain_board(choice["board"]))
        last = _write_report(goal, model, folder, trace, choice)
    return last


def _default_goal():
    recent = ledger.recent(1)
    if recent and recent[-1].get("summary"):
        return "From the latest journal line, choose the next useful vault note: " + recent[-1]["summary"][:180]
    return "Choose the next useful note to write in the vault."


def _explore(goal, branches, refine, model):
    nodes = []
    for branch in range(branches):
        parent_id = ""
        parent_text = ""
        for attempt in range(refine + 1):
            text = _attempt(model, goal, branch, attempt, parent_text)
            score = _score(model, goal, text)
            node = dream_rsi.make_node(branch, attempt, score, text, parent_id)
            nodes.append(node)
            parent_id = node["id"]
            parent_text = text
    return {"goal": goal, "model": model, "nodes": nodes}


def _attempt(model, goal, branch, attempt, parent_text):
    system = (
        "You are writing one attempt in a local search tree. "
        "One short paragraph. Name an existing command only from this set: "
        "ask, dream, parallel, choose, journal, status. "
        "Do not propose a git push or a shell command."
    )
    user = "Goal:\n%s\n\nBranch %d attempt %d." % (goal, branch, attempt)
    if parent_text:
        user += "\n\nRevise the parent attempt. Change one thing.\n" + parent_text[:1200]
    return ollama_client.chat(
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=180,
        temperature=0.4,
        num_predict=280,
    )


def _score(model, goal, text):
    raw = ollama_client.chat(
        model,
        [
            {
                "role": "system",
                "content": "Score the attempt from 0 to 1 for progress on the goal. "
                "Reply with JSON only: {\"score\":0.0,\"because\":\"\"}.",
            },
            {"role": "user", "content": "Goal:\n%s\n\nAttempt:\n%s" % (goal[:800], text[:1200])},
        ],
        timeout=120,
        temperature=0.0,
        num_predict=120,
    )
    return _parse_score(raw)


def _parse_score(raw):
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            score = float(json.loads(raw[start : end + 1]).get("score", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            score = 0.0
    else:
        score = 0.0
    return max(0.0, min(1.0, score))


def _next_index(worlds):
    if not os.path.isdir(worlds):
        return 0
    nums = []
    for name in os.listdir(worlds):
        if name.startswith("iter") and name[4:].isdigit():
            nums.append(int(name[4:]))
    return max(nums) + 1 if nums else 0


def _plain_board(board):
    plain = {}
    for name, row in board.items():
        plain[name] = {key: row[key] for key in ("reward", "auc", "penalty", "scored")}
    return plain


def _write_report(goal, model, folder, trace, choice):
    best = max(trace["nodes"], key=lambda node: (node["score"], node["id"]))
    stamp = time.strftime("%Y%m%d-%H%M")
    name = "dreams/%s-dream.md" % stamp
    lines = [
        "# Dream",
        "",
        "Method: Dream-RSI replay. Paper: Zheng et al., arXiv:2609.14858.",
        "",
        "## Measured",
        "",
        "- Goal: %s" % goal[:300],
        "- Model: %s" % (model or "none"),
        "- World: `%s`" % os.path.basename(folder),
        "- Nodes: %d" % len(trace["nodes"]),
        "- Promoted policy: %s" % choice["promoted"],
        "- Incumbent kept: %s" % ("yes" if choice["kept"] else "no"),
        "",
        "## Replay reward",
        "",
    ]
    for policy, row in choice["board"].items():
        lines.append("- %s: reward %.4f, auc %.4f, traces %d" % (policy, row["reward"], row["auc"], row["scored"]))
    lines.extend(
        [
            "",
            "## Best attempt",
            "",
            "- %s score %.2f" % (best["id"], best["score"]),
            "",
            best["text"].strip(),
            "",
        ]
    )
    vault.write(name, "\n".join(lines))
    proposal = "%s promoted; best %s scored %.2f" % (choice["promoted"], best["id"], best["score"])
    proposals = vault.read("dreams/PROPOSALS.md")
    if not proposals:
        proposals = "# Proposals\n\nReplay promotes a policy. Nothing here edits the program.\n\n"
    proposals += "- %s — %s (see [[%s]])\n" % (stamp, proposal, name)
    vault.write("dreams/PROPOSALS.md", proposals)
    event = ledger.append(
        "dream",
        proposal,
        {"note": name, "policy": choice["promoted"], "world": os.path.basename(folder), "model": model},
    )
    return {
        "note": name,
        "proposal": proposal,
        "policy": choice["promoted"],
        "kept": choice["kept"],
        "model": model,
        "world": os.path.basename(folder),
        "event": event["id"],
        "board": _plain_board(choice["board"]),
    }
