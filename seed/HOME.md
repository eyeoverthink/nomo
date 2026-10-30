# NoMo

This vault is the memory. The chat window is not.

- [[SELF]] is what this process is allowed to claim.
- [[USER]] is the operator card. Edit it. Conclusions live in [[peers/operator]].
- [[peers/self]] holds this agent's conclusions about its own limits.
- Dreams land in `dreams/`. They are proposals. The next run reads them.
- `journal/events.jsonl` is the hash chain. Read it before claiming a past action.

## Commands

- `python nomo.py setup` show which public models are installed
- `python nomo.py status` show the tiers this process selected
- `python nomo.py ask "..."` one turn
- `python nomo.py chat` several turns, until a blank line
- `python nomo.py dream` write the next dream file
- `python nomo.py parallel "..."` scout, critic, and builder, then a merge
- `python nomo.py replicate <name>` copy a child under `children/`
- `python nomo.py choose "question" optionA optionB` an uncalibrated local choice
- `python nomo.py watch --max 1` run the dream a bounded number of times
- `python nomo.py journal` show recent events
