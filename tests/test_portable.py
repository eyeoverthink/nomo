"""Portable behavior that must hold on a machine with no Ollama daemon."""

import os
import unittest

from nomo import agent, honcho, runbox, select
from nomo.doctor import missing
from nomo.paths import find_root

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEEDLES = (
    "Vau" + "ghn",
    "Oak" + "land",
    "eye" + "overthink",
    "fray" + "nix",
    "FRAY" + "NIX",
    "F:\\Full",
    "F:/Full",
    "C:\\Users",
    "niles@",
)


def _local(name, size, remote=""):
    return {"name": name, "size": size, "remote_host": remote}


class SelectTests(unittest.TestCase):
    def test_public_reason_beats_a_private_local_tag(self):
        inventory = [
            _local("custom-dreamer:8b", 4_920_000_000),
            _local("llama3.1:8b", 4_920_000_000),
            _local("llama3.2:latest", 2_019_000_000),
        ]
        self.assertEqual(
            select.choose(inventory, "llama3.1:8b", select.PUBLIC_REASON, "reason"),
            "llama3.1:8b",
        )

    def test_cloud_stub_is_refused_even_when_pinned(self):
        inventory = [
            _local("gpt-oss:120b-cloud", 307, "https://ollama.com"),
            _local("custom-dreamer:120b", 6472, "https://ollama.com:443"),
        ]
        self.assertEqual(select.choose(inventory, "gpt-oss:120b-cloud", [], "reason"), "")
        self.assertEqual(select.choose(inventory, "custom-dreamer:120b", select.PUBLIC_REASON, "reason"), "")

    def test_heavy_local_is_not_the_automatic_choice(self):
        inventory = [_local("llama3:70b", 40_000_000_000)]
        self.assertEqual(select.choose(inventory, "llama3.1:8b", ["llama3.1:8b"], "reason"), "")

    def test_explicit_heavy_pin_is_allowed(self):
        inventory = [_local("llama3:70b", 40_000_000_000)]
        self.assertEqual(select.choose(inventory, "llama3:70b", [], "reason"), "llama3:70b")

    def test_only_custom_local_model_still_runs(self):
        inventory = [_local("my-model:latest", 2_000_000_000)]
        self.assertEqual(
            select.choose(inventory, "llama3.2:latest", ["llama3.2:latest"], "route"),
            "my-model:latest",
        )

    def test_route_picks_the_smallest_chat_model(self):
        inventory = [
            _local("big:latest", 5_000_000_000),
            _local("small:latest", 1_500_000_000),
            _local("nomic-embed-text:latest", 274_000_000),
        ]
        self.assertEqual(select.choose(inventory, "missing:latest", ["missing:latest"], "route"), "small:latest")

    def test_reason_skips_an_embed_name(self):
        inventory = [
            _local("nomic-embed-text:latest", 274_000_000),
            _local("custom:latest", 2_000_000_000),
        ]
        self.assertEqual(select.choose(inventory, "llama3.1:8b", ["llama3.1:8b"], "reason"), "custom:latest")

    def test_embed_prefers_the_public_embed_model(self):
        inventory = [
            _local("llama3.2:latest", 2_000_000_000),
            _local("nomic-embed-text:latest", 274_000_000),
        ]
        self.assertEqual(
            select.choose(inventory, "nomic-embed-text:latest", select.PUBLIC_EMBED, "embed"),
            "nomic-embed-text:latest",
        )

    def test_untagged_name_prefers_a_light_tag(self):
        inventory = [
            _local("llama3.2:70b", 40_000_000_000),
            _local("llama3.2:1b", 1_200_000_000),
        ]
        self.assertEqual(select.choose(inventory, "llama3.2", [], "route"), "llama3.2:1b")

    def test_missing_exact_tag_uses_the_fallback(self):
        inventory = [
            _local("llama3.2:1b", 1_200_000_000),
            _local("llama3.1:8b", 4_900_000_000),
        ]
        self.assertEqual(
            select.choose(inventory, "llama3.2:latest", ["llama3.1:8b"], "route"),
            "llama3.1:8b",
        )


class DoctorTests(unittest.TestCase):
    def test_missing_pulls_when_the_disk_is_empty(self):
        self.assertEqual(missing([]), ["llama3.2", "llama3.1:8b", "nomic-embed-text"])

    def test_llama3_satisfies_the_reason_pull(self):
        inventory = [_local("llama3:latest", 4_900_000_000), _local("llama3.2:latest", 2_000_000_000)]
        self.assertEqual(missing(inventory), ["nomic-embed-text"])

    def test_cloud_stub_does_not_count_as_installed(self):
        inventory = [_local("llama3.2:latest", 307, "https://ollama.com")]
        self.assertIn("llama3.2", missing(inventory))


class BoundaryTests(unittest.TestCase):
    def test_vault_rejects_escape(self):
        from nomo import vault

        with self.assertRaises(ValueError):
            vault._safe_name("../outside.md")
        with self.assertRaises(ValueError):
            vault._safe_name("notes/../../outside.md")

    def test_peer_slug_stays_inside_peers(self):
        self.assertEqual(honcho._file("Operator"), "peers/operator.md")
        self.assertEqual(honcho._file("../../etc/passwd"), "peers/etcpasswd.md")
        self.assertNotIn("..", honcho._file(".."))

    def test_default_peer_is_generic(self):
        previous = os.environ.pop("NOMO_OPERATOR", None)
        try:
            slug, title = honcho.operator_id()
        finally:
            if previous is not None:
                os.environ["NOMO_OPERATOR"] = previous
        self.assertEqual(slug, "operator")
        self.assertEqual(title, "Operator")

    def test_model_tools_exclude_shell_and_replication(self):
        from nomo import tools

        self.assertNotIn("run", tools.TOOLS)
        self.assertNotIn("shell", tools.TOOLS)
        self.assertNotIn("replicate", tools.TOOLS)
        self.assertNotIn("dream", tools.TOOLS)

    def test_run_denylist(self):
        self.assertFalse(runbox.allowed(["git", "push", "origin", "main"]))
        self.assertFalse(runbox.allowed(["rm", "-rf", "/"]))
        self.assertFalse(runbox.allowed([]))
        self.assertTrue(runbox.allowed(["python", "-c", "print(1)"]))

    def test_run_stays_off_without_the_env_flag(self):
        previous = os.environ.pop("NOMO_ALLOW_RUN", None)
        try:
            with self.assertRaises(PermissionError):
                runbox.execute(["python", "-c", "print(1)"])
        finally:
            if previous is not None:
                os.environ["NOMO_ALLOW_RUN"] = previous

    def test_prompt_names_the_model_it_was_given(self):
        text = agent.system_prompt("llama3.1:8b")
        self.assertIn("llama3.1:8b", text)
        for needle in NEEDLES:
            self.assertNotIn(needle, text)

    def test_root_can_be_pointed_at_another_directory(self):
        previous = os.environ.get("NOMO_ROOT")
        os.environ["NOMO_ROOT"] = ROOT
        try:
            self.assertEqual(os.path.normcase(find_root()), os.path.normcase(ROOT))
            self.assertTrue(os.path.isfile(os.path.join(find_root(), "seed", "HOME.md")))
        finally:
            if previous is None:
                os.environ.pop("NOMO_ROOT", None)
            else:
                os.environ["NOMO_ROOT"] = previous


class TreeTests(unittest.TestCase):
    def test_published_tree_has_no_machine_identity(self):
        skip = {".git", ".venv", "vault", "children", "__pycache__"}
        allowed = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".example"}
        hits = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [name for name in dirnames if name not in skip]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext not in allowed and name not in {".gitignore", ".gitattributes"} and not name.endswith(".Modelfile"):
                    continue
                path = os.path.join(dirpath, name)
                if os.path.basename(path) == "test_portable.py":
                    continue
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                for needle in NEEDLES:
                    if needle not in text:
                        continue
                    # The clone URL names the GitHub account. Runtime identity stays generic.
                    if needle == ("eye" + "overthink") and os.path.basename(path) == "README.md":
                        continue
                    hits.append(os.path.relpath(path, ROOT) + ":" + needle)
        self.assertEqual(hits, [])

    def test_readme_tells_a_clone_how_to_run(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        for phrase in (
            "llama3.2",
            "llama3.1:8b",
            "nomic-embed-text",
            "python nomo.py setup",
            "cactus-needle",
            "vault/",
            "journal",
            "NOMO_ROUTE_MODEL",
            "NOMO_REASON_MODEL",
        ):
            self.assertIn(phrase, text)
