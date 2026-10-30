"""Project paths and public model defaults.

Paths resolve to this repository, or to the current directory when the
package is installed somewhere else. Model names are public Ollama tags.
A local .env file can override them without being committed.
"""

import os

ROUTE_DEFAULT = "llama3.2:latest"
REASON_DEFAULT = "llama3.1:8b"
EMBED_DEFAULT = "nomic-embed-text:latest"
OLLAMA_DEFAULT = "http://127.0.0.1:11434"


def find_root():
    env = os.environ.get("NOMO_ROOT", "").strip()
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "nomo.py")) or os.path.isdir(os.path.join(parent, "seed")):
        return parent
    return os.path.abspath(os.getcwd())


def _load_dotenv(root):
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


ROOT = find_root()
_load_dotenv(ROOT)

VAULT = os.path.join(ROOT, "vault")
SEED = os.path.join(ROOT, "seed")
CHILDREN = os.path.join(ROOT, "children")
JOURNAL = os.path.join(VAULT, "journal")
DREAMS = os.path.join(VAULT, "dreams")
PEERS = os.path.join(VAULT, "peers")
NOTES = os.path.join(VAULT, "notes")
SKILLS = os.path.join(VAULT, "skills")

ROUTE_MODEL = os.environ.get("NOMO_ROUTE_MODEL", ROUTE_DEFAULT)
REASON_MODEL = os.environ.get("NOMO_REASON_MODEL", REASON_DEFAULT)
EMBED_MODEL = os.environ.get("NOMO_EMBED_MODEL", EMBED_DEFAULT)
OLLAMA = os.environ.get("OLLAMA_HOST", OLLAMA_DEFAULT)
