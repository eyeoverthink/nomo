"""Local memory, public-page checks, and the evolve source guard."""

import os
import tempfile
import unittest

from nomo import absorb, evolve, graph, record


class RecordTests(unittest.TestCase):
    def test_seal_chain_detects_a_break(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "record.jsonl")
            record.seal("ask", "one", path=path)
            record.seal("ask", "two", path=path)
            self.assertTrue(record.verify(path)["ok"])
            self.assertEqual(record.verify(path)["count"], 2)
            with open(path, encoding="utf-8") as handle:
                lines = handle.readlines()
            lines[0] = lines[0].replace("one", "edited")
            with open(path, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
            self.assertFalse(record.verify(path)["ok"])


class GraphTests(unittest.TestCase):
    def test_lookup_finds_a_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "graph.sqlite")
            graph.remember("vault layout", "Notes live beside the code.", "decision", "rec-1", path=path)
            rows = graph.lookup("vault notes", path=path)
            self.assertEqual(rows[0]["name"], "vault layout")
            self.assertEqual(graph.count(path), 1)


class AbsorbTests(unittest.TestCase):
    def test_private_and_non_web_targets_are_refused(self):
        for url in (
            "file:///tmp/x",
            "http://127.0.0.1/secret",
            "http://localhost/x",
            "http://10.1.2.3/x",
            "http://169.254.169.254/latest",
            "http://192.168.0.1/",
        ):
            with self.assertRaises(ValueError):
                absorb.public_target(url)


class EvolveTests(unittest.TestCase):
    def test_source_guard_blocks_a_shell_and_a_disassembler(self):
        self.assertEqual(evolve.blocked("print(1 + 1)\nassert True\n"), "")
        self.assertEqual(evolve.blocked("import subprocess\nsubprocess.call(['id'])\n"), "subprocess")
        self.assertIn("ghidra", evolve.blocked("import ghidra"))

    def test_executor_stays_off_without_the_flag(self):
        previous = os.environ.pop("NOMO_ALLOW_RUN", None)
        try:
            result = evolve._run("print(1)\n", "job")
        finally:
            if previous is not None:
                os.environ["NOMO_ALLOW_RUN"] = previous
        self.assertFalse(result["ran"])

    def test_code_fence_is_extracted(self):
        text = "Here:\n```python\nprint(2)\n```\n"
        self.assertEqual(evolve.extract_code(text), "print(2)")
