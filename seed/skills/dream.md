# Dream-RSI

`python nomo.py dream` reads the last journal lines and writes `vault/dreams/<stamp>-dream.md`.

The recursion is the next run reading that file. The pass writes a proposal. It leaves `nomo/*.py` untouched, opens no shell, and pushes no remote.

`python nomo.py watch --max N` repeats the dream at most N times, and N cannot exceed 24. It is an operator command. It is not a startup service.
