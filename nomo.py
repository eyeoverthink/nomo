"""Run NoMo from a clone without installing the package.

    python nomo.py setup
    python nomo.py status
    python nomo.py ask "what is in the vault?"
    python nomo.py chat
    python nomo.py dream
    python nomo.py parallel "how should the vault be organized"
    python nomo.py choose "which note first" HOME.md SELF.md
    python nomo.py replicate scout
    python nomo.py watch --max 1
    python nomo.py journal
"""

import sys

from nomo.cli import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("nomo: " + str(exc), file=sys.stderr)
        sys.exit(1)
