"""Operator command runner.

This is not a model tool. It runs only when the operator sets NOMO_ALLOW_RUN=1
for that process. The working directory is the repository root. The denylist
blocks the obvious destructive forms. It is not a security sandbox.
"""

import os
import subprocess

from nomo.paths import ROOT

_BLOCK = (
    "git push",
    "git config",
    "shutdown",
    "reboot",
    "diskpart",
    "mkfs",
    "format-volume",
    "clear-disk",
    "cipher ",
    "del /s",
    "rmdir /s",
    "rm -rf",
    "rm -fr",
    "remove-item",
    "invoke-expression",
    "encodedcommand",
    " -enc",
    "reg delete",
    "dd if=",
    ":(){",
)


def allowed(argv):
    if not argv:
        return False
    text = " ".join(str(part) for part in argv).lower()
    for item in _BLOCK:
        if item in text:
            return False
    return True


def execute(argv, timeout=60):
    if os.environ.get("NOMO_ALLOW_RUN", "") != "1":
        raise PermissionError("Set NOMO_ALLOW_RUN=1 for this process to run a command.")
    if not allowed(argv):
        raise PermissionError("That command is blocked.")
    limit = max(1, min(int(timeout), 120))
    try:
        proc = subprocess.run(
            [str(part) for part in argv],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=limit,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "code": 124,
            "stdout": (exc.stdout or "")[:8000],
            "stderr": (exc.stderr or "timed out")[:8000],
        }
    return {
        "code": proc.returncode,
        "stdout": (proc.stdout or "")[:8000],
        "stderr": (proc.stderr or "")[:8000],
    }
