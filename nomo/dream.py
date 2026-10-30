"""Dream-RSI.

One pass reads the journal and the self card, writes a dream note, and appends
a single proposal. It does not edit Python, does not run a shell, and does not
push git. The next session reads the dream. That is the recursion.
"""

import os
import time

from nomo import ledger, ollama_client, vault
from nomo.paths import DREAMS


PROMPT = """You are the dream pass of a local agent. You are not a larger model than the one running this call.
Read the journal and write a markdown dream with these sections only:
# Dream
## What repeated
## What failed
## One experiment to try next
The experiment must be something the operator can run with the existing commands (ask, dream, parallel, journal, status).
Do not propose a git push, a new privilege, or a hidden startup. Do not invent a person's name.
Tag any claim you did not see in the journal as [recall]. Tag claims taken from the journal as [measured].
"""


def run():
    vault.ensure()
    os.makedirs(DREAMS, exist_ok=True)
    events = ledger.recent(12)
    self_card = vault.read("peers/self.md")
    home = vault.read("HOME.md")
    packet = {
        "journal": events,
        "self": self_card[-1500:],
        "home": home[:800],
    }
    model = ollama_client.reason_model()
    text = ollama_client.chat(
        model,
        [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": str(packet)},
        ],
        timeout=240,
        temperature=0.5,
        num_predict=700,
    )
    stamp = time.strftime("%Y%m%d-%H%M")
    name = "dreams/%s-dream.md" % stamp
    body = text.strip() + "\n\nmodel: %s\n" % model
    vault.write(name, body)
    proposal = _proposal(text)
    proposals = vault.read("dreams/PROPOSALS.md")
    if not proposals:
        proposals = "# Proposals\n\nThese are notes. Nothing here runs by itself.\n\n"
    proposals += "- %s — %s (see [[%s]])\n" % (stamp, proposal, name)
    vault.write("dreams/PROPOSALS.md", proposals)
    event = ledger.append("dream", proposal, {"note": name, "model": model})
    return {"note": name, "proposal": proposal, "model": model, "event": event["id"]}


def _proposal(text):
    for line in text.splitlines():
        if line.lower().startswith("## one experiment"):
            continue
        if line.strip().startswith("- ") and "experiment" in text.lower():
            return line.strip()[2:240]
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return (lines[-1] if lines else "No experiment was written.")[:240]
