"""Local Dream-RSI loop.

The loop is the one in Zheng, Wu, Zhang, et al., "Dream-RSI: Recursive
Self-Improvement through Evolving Worlds" (arXiv:2609.14858, 2026).

    https://github.com/zhengkid/Dream-RSI
    https://github.com/google-research/dream-rsi

Online exploration writes a small tree of attempts and stores each score.
Offline dreaming replays exploration policies on that frozen tree. The
replay reads saved scores and does not call the model again. The policy
with the higher replay reward is promoted. The incumbent stays when it
ties or wins.

The paper's coding agent is Gemini, and its evaluator runs the candidate
program. This module uses the local Ollama model as the writer and a
local 0–1 score as the outcome. The policy is one of three interpreters.
A model reply cannot become a Python program.
"""

import json
import os

POLICIES = ("parallel_refine", "best_first", "wide")
INCUMBENT = "parallel_refine"
RHOS = (0.25, 0.5, 0.75, 1.0)
PENALTY = 0.05


def node_id(branch, attempt):
    return "b%d_a%d" % (int(branch), int(attempt))


def make_node(branch, attempt, score, text="", parent=""):
    return {
        "id": node_id(branch, attempt),
        "branch": int(branch),
        "attempt": int(attempt),
        "parent": parent or "",
        "score": max(0.0, min(1.0, float(score))),
        "text": text or "",
    }


class ReplayEnv:
    """Read-only view of a finished discovery tree."""

    def __init__(self, nodes):
        self.nodes = {node["id"]: node for node in nodes}
        self.revealed = set()
        self.budget_spent = 0
        self.best_so_far = 0.0
        self.decision_rounds = 0
        self.batch_sizes = []

    def legal(self):
        found = []
        for node in self.nodes.values():
            if node["id"] in self.revealed:
                continue
            parent = node.get("parent") or ""
            if node["attempt"] > 0:
                parent = parent or node_id(node["branch"], node["attempt"] - 1)
                if parent not in self.revealed:
                    continue
            found.append(node)
        found.sort(key=lambda node: (node["attempt"], node["branch"]))
        return found

    def probe_batch(self, ids):
        legal_ids = {node["id"] for node in self.legal()}
        clean = []
        for nid in ids:
            if nid in legal_ids and nid not in clean:
                clean.append(nid)
        if not clean:
            return []
        self.decision_rounds += 1
        self.batch_sizes.append(len(clean))
        for nid in clean:
            self.revealed.add(nid)
            self.budget_spent += 1
            self.best_so_far = max(self.best_so_far, float(self.nodes[nid]["score"]))
        return clean


def run_policy(name, nodes, budget):
    if name not in POLICIES:
        raise KeyError(name)
    env = ReplayEnv(nodes)
    cap = max(0, int(budget))
    if name == "wide":
        roots = [node["id"] for node in env.legal() if node["attempt"] == 0]
        env.probe_batch(roots[:cap])
        return env
    if name == "parallel_refine":
        attempt = 0
        while env.budget_spent < cap:
            cells = [node["id"] for node in env.legal() if node["attempt"] == attempt]
            if not cells:
                if not env.legal():
                    break
                attempt += 1
                continue
            env.probe_batch(cells[: cap - env.budget_spent])
            attempt += 1
        return env
    while env.budget_spent < cap:
        legal = env.legal()
        if not legal:
            break
        choice = None
        refinements = [node for node in legal if node["attempt"] > 0]
        if env.revealed and refinements:
            best_id = max(
                env.revealed,
                key=lambda nid: (float(env.nodes[nid]["score"]), -env.nodes[nid]["branch"]),
            )
            branch = env.nodes[best_id]["branch"]
            same = [node for node in refinements if node["branch"] == branch]
            if same:
                same.sort(key=lambda node: node["attempt"])
                choice = same[0]["id"]
        if choice is None:
            roots = [node for node in legal if node["attempt"] == 0]
            roots.sort(key=lambda node: node["branch"])
            choice = (roots or legal)[0]["id"]
        env.probe_batch([choice])
    return env


def _attainment(best, run_best):
    if run_best <= 0:
        return 0.0
    return max(0.0, min(float(best) / float(run_best), 1.0))


def _auc(points, ref):
    if ref <= 0 or not points:
        return 0.0
    best_by_budget = {}
    for budget, attain in sorted(points, key=lambda item: (item[0], -item[1])):
        if budget not in best_by_budget or attain > best_by_budget[budget]:
            best_by_budget[budget] = attain
    area = 0.0
    previous = 0.0
    for budget in sorted(best_by_budget):
        attain = best_by_budget[budget]
        if attain > previous:
            area += (attain - previous) * max(0.0, ref - budget)
            previous = attain
    return area / ref


def reward(name, traces):
    areas = []
    penalties = []
    for trace in traces:
        nodes = trace.get("nodes") or []
        if len(nodes) < 2:
            continue
        run_best = max(float(node["score"]) for node in nodes)
        if run_best <= 0:
            continue
        ref = float(len(nodes))
        points = []
        ratios = []
        for rho in RHOS:
            cap = max(1, int(round(rho * ref)))
            env = run_policy(name, nodes, cap)
            points.append((float(env.budget_spent), _attainment(env.best_so_far, run_best)))
            if env.budget_spent:
                ratios.append(env.decision_rounds / float(env.budget_spent))
        areas.append(_auc(points, ref))
        penalties.append(sum(ratios) / len(ratios) if ratios else 1.0)
    if not areas:
        return {"reward": 0.0, "auc": 0.0, "penalty": 1.0, "scored": 0}
    auc = sum(areas) / len(areas)
    penalty = sum(penalties) / len(penalties)
    return {
        "reward": auc - PENALTY * penalty,
        "auc": auc,
        "penalty": penalty,
        "scored": len(areas),
    }


def select_policy(traces, incumbent=INCUMBENT):
    if incumbent not in POLICIES:
        incumbent = INCUMBENT
    board = {name: reward(name, traces) for name in POLICIES}
    promoted = max(POLICIES, key=lambda name: (board[name]["reward"], 1 if name == incumbent else 0))
    return {
        "incumbent": incumbent,
        "promoted": promoted,
        "kept": promoted == incumbent,
        "board": board,
    }


def load_policy(path):
    if not path or not os.path.isfile(path):
        return INCUMBENT
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return INCUMBENT
    name = data.get("name") if isinstance(data, dict) else ""
    return name if name in POLICIES else INCUMBENT


def save_policy(path, name, board):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"name": name, "board": board, "method": "dream-rsi-replay"}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def write_trace(directory, trace):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "raw_scores.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(trace, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def read_trace(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise ValueError("A replay world needs a nodes list.")
    return data


def list_traces(worlds_dir):
    found = []
    if not os.path.isdir(worlds_dir):
        return found
    for name in sorted(os.listdir(worlds_dir)):
        path = os.path.join(worlds_dir, name, "raw_scores.json")
        if os.path.isfile(path):
            found.append(read_trace(path))
    return found
