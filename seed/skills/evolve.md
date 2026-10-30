# Evolve

`python nomo.py evolve "task"` runs three roles in order:

- Architect writes one Python file.
- Critic names a defect, or says the asserts match the task.
- Executor runs that file when `NOMO_ALLOW_RUN=1`. The working directory is `vault/sandbox`.

A passing run is stored in `vault/fossils/` and as a module row in the SQLite graph. The next session reads that fossil. The cycle does not change `nomo/*.py` and does not push git.

Set `NOMO_CODE_MODEL` to pick the writer. A public coder tag is used when Ollama has one.
