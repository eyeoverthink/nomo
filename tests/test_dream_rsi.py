"""Replay behavior of the local Dream-RSI loop. No model calls."""

import json
import os
import tempfile
import unittest

from nomo import dream_rsi


def _tree():
    return [
        dream_rsi.make_node(0, 0, 0.4, "root a"),
        dream_rsi.make_node(0, 1, 0.9, "refine a", "b0_a0"),
        dream_rsi.make_node(1, 0, 0.1, "root b"),
    ]


class ReplayTests(unittest.TestCase):
    def test_replay_reads_frozen_scores(self):
        nodes = _tree()
        before = [node["score"] for node in nodes]
        env = dream_rsi.run_policy("best_first", nodes, 3)
        self.assertEqual([node["score"] for node in nodes], before)
        self.assertAlmostEqual(env.best_so_far, 0.9)
        self.assertEqual(env.budget_spent, 3)

    def test_child_stays_closed_until_its_parent_is_open(self):
        env = dream_rsi.ReplayEnv(_tree())
        self.assertEqual(env.probe_batch(["b0_a1"]), [])
        self.assertEqual(env.budget_spent, 0)
        opened = env.probe_batch(["b0_a0", "b0_a1"])
        self.assertEqual(opened, ["b0_a0"])
        self.assertAlmostEqual(env.best_so_far, 0.4)

    def test_unknown_node_is_ignored(self):
        env = dream_rsi.ReplayEnv(_tree())
        self.assertEqual(env.probe_batch(["missing"]), [])
        self.assertEqual(env.budget_spent, 0)

    def test_best_first_beats_wide_on_a_deep_score(self):
        traces = [{"nodes": _tree()}]
        deep = dream_rsi.reward("best_first", traces)
        wide = dream_rsi.reward("wide", traces)
        self.assertGreater(deep["reward"], wide["reward"])
        self.assertEqual(deep["scored"], 1)

    def test_tie_keeps_the_incumbent(self):
        traces = []
        choice = dream_rsi.select_policy(traces, "wide")
        self.assertEqual(choice["promoted"], "wide")
        self.assertTrue(choice["kept"])

    def test_a_better_policy_is_promoted(self):
        choice = dream_rsi.select_policy([{"nodes": _tree()}], "wide")
        self.assertEqual(choice["promoted"], "best_first")
        self.assertFalse(choice["kept"])

    def test_world_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = dream_rsi.write_trace(folder, {"goal": "note", "nodes": _tree()})
            loaded = dream_rsi.read_trace(path)
            self.assertEqual(len(loaded["nodes"]), 3)
            policy = os.path.join(folder, "policy.json")
            dream_rsi.save_policy(policy, "best_first", {"best_first": {"reward": 0.5}})
            self.assertEqual(dream_rsi.load_policy(policy), "best_first")
            with open(path, encoding="utf-8") as handle:
                json.load(handle)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(KeyError):
            dream_rsi.run_policy("generated-code", _tree(), 1)
