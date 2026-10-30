# NoMo

NoMo is a local agent you run on your own machine. It talks to [Ollama](https://ollama.com) for language, can route a tool through [Needle 3](https://pypi.org/project/cactus-needle/) when you install that package, and keeps its memory in files next to the code.

A clone is the whole program. It does not read a private model list, a home-directory path, or an operator name out of the source. On first launch it copies `seed/` into `vault/` and selects whatever public Ollama models are installed. If those are missing and some other local model is present, it uses that model and says so.

```text
python nomo.py setup
python nomo.py status
python nomo.py ask "What is in the vault?"
```

## What you need

- Python 3.10 or newer
- [Ollama](https://ollama.com/download), running locally
- Disk space for the models you pull

Needle 3 is optional. Chat, dreams, and keyword search work without it.

## Install

Clone the repository and enter it. The vault is created in that directory.

Windows, PowerShell:

```powershell
git clone https://github.com/eyeoverthink/nomo.git
cd nomo
python nomo.py setup
```

macOS and Linux:

```bash
git clone https://github.com/eyeoverthink/nomo.git
cd nomo
python3 nomo.py setup
```

`setup` prints the route model, the reason model, the embed model, and the public pulls that are still missing. It does not download weights until you ask.

Pull the three public defaults:

```bash
python nomo.py setup --pull
```

That runs, only for the tags that are absent:

```bash
ollama pull llama3.2
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

`llama3.2` is the small route model. `llama3.1:8b` writes answers and dreams. `nomic-embed-text` embeds notes for search. Any one of `llama3`, `llama3:8b`, or `llama3.1:latest` satisfies the reason slot, so a machine that already has `llama3` does not need a second 8B download.

Install the optional tool router:

```bash
python nomo.py setup --with-needle
```

That creates `.venv` when it is missing and installs `cactus-needle` from `requirements.txt`. The first Needle call downloads its small weight into the Hugging Face cache for that user (`~/.cache/cactus-needle/`). Later calls stay on disk. Set `HF_TOKEN` if you want a higher Hugging Face rate limit. The variable is optional.

Use the virtualenv interpreter when you want Needle on the turn:

```powershell
.\.venv\Scripts\python.exe nomo.py ask "search the vault for the operator"
```

```bash
.venv/bin/python nomo.py ask "search the vault for the operator"
```

The standard-library interpreter still runs the agent. `status` reports `installed-in-.venv` when Needle is in the virtualenv and the current interpreter is a different Python.

## Models

| Tier | Public default | Role |
| --- | --- | --- |
| Route | `llama3.2:latest` | Decides whether a tool is needed |
| Reason | `llama3.1:8b` | Writes the answer and the dream |
| Embed | `nomic-embed-text:latest` | Indexes notes. Keyword search works without it |
| Needle 3 | `cactus-needle` 3.2.8 | Optional CQ2 tool router, about 29–121M parameters |

Selection order:

1. The tag in `NOMO_ROUTE_MODEL`, `NOMO_REASON_MODEL`, or `NOMO_EMBED_MODEL`, when that tag is a weight on disk.
2. The public ladder in the table, then `llama3`, `mistral`, `qwen2.5:7b`, `gemma2`, `phi3:mini`, and the other names in `nomo/select.py`.
3. Any other local chat model. The route tier prefers the smallest. The reason tier prefers one of at least 3 GB when one exists.

A tag is skipped when Ollama marks it as a remote model, when its name contains `cloud`, when the blob is under 1 MB, or when the tag is `70b`, `72b`, `120b`, or `405b`. Pin a large local weight with an environment variable when you want it. A cloud stub is refused even if it is pinned.

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
export NOMO_ROUTE_MODEL=llama3.2:latest
export NOMO_REASON_MODEL=llama3.1:8b
export NOMO_EMBED_MODEL=nomic-embed-text:latest
export NOMO_OPERATOR=
```

On Windows PowerShell, set the same names with `$env:NOMO_ROUTE_MODEL = "llama3.2:latest"`. A file named `.env` in the repository is read for any name that is not already in the environment. Copy `.env.example`. `.env` is gitignored.

`python nomo.py models` prints the tag chosen for each tier, the local tags, and the skipped tags.

Optional named aliases, after the base models are pulled:

```bash
ollama create nomo-route -f modelfiles/nomo-route.Modelfile
ollama create nomo-reason -f modelfiles/nomo-reason.Modelfile
```

The program does not require those aliases. The per-request prompt carries the same rules.

## Commands

| Command | What it does |
| --- | --- |
| `python nomo.py setup` | Show which public models are installed |
| `python nomo.py setup --pull` | Pull the missing public models |
| `python nomo.py setup --with-needle` | Create `.venv` and install Needle 3 |
| `python nomo.py status` | Show the tiers this process selected and check the journal |
| `python nomo.py models` | List local tags and skipped tags |
| `python nomo.py ask "..."` | One turn |
| `python nomo.py chat` | Turns until a blank line |
| `python nomo.py dream` | Write one dream note and one proposal |
| `python nomo.py parallel "..."` | Scout, critic, and builder, then a merge |
| `python nomo.py choose "question" A B` | Typed choice with an uncalibrated score |
| `python nomo.py replicate <name>` | Copy a stopped child under `children/` |
| `python nomo.py watch --max 1` | Repeat the dream at most 24 times, then exit |
| `python nomo.py journal` | Print recent journal events |
| `python nomo.py run -- <command>` | Operator shell, off unless `NOMO_ALLOW_RUN=1` |

`watch --every` defaults to 1800 seconds and will not go below 30. The process is not a service. Close the terminal and it stops.

## One turn

1. The question is appended to the journal.
2. Needle 3 routes a tool when `import needle` works and it returns a call. Otherwise `llama3.2` may return one JSON tool call, up to three rounds.
3. The reason model writes one short paragraph from `SELF.md`, `USER.md`, the peer cards, the open proposals, the last journal lines, and the tool results.

Tool results are marked for the model as measured. Anything the model adds from outside those files is marked recall. The reply names the model that produced it.

Tools the model may call: `status`, `vault_search`, `vault_read`, `vault_write`, `peer_note`, `peer_read`, `ledger_recent`, `list_files`, `read_file`.

Paths that leave the repository are refused. A file over 200000 bytes is refused. `list_files` skips `.venv`, `.git`, `children`, and dot names.

## Memory

Three stores, all under the clone:

- **Vault.** Markdown and wikilinks in `vault/`, the same shape as an Obsidian folder. `seed/` is the published starting set. First launch copies a seed file only when that file is missing, so later edits to your vault stay put.
- **Peer cards.** `vault/peers/operator.md` and `vault/peers/self.md`. A conclusion looks like `- [0.60] Prefers a file over a longer note. evidence: jev-abc123`. The number is a weight you or a dream pass wrote down.
- **Journal.** `vault/journal/events.jsonl` is a hash chain. Each line stores the hash of the previous line. `status` reports `journal_ok`. An id starts with `jev-` so a reader can see it came from this log.

`vault/`, `children/`, and `.venv/` are gitignored. A clone wakes up from `seed/`, then grows its own vault. Move `vault/` aside and run again to recopy the seed.

Set `NOMO_OPERATOR` before the first run if the peer card should use a name you choose. With the variable unset, the card title is `Operator`, and the local account name is written once into `vault/USER.md` in place of the seed marker.

`NOMO_ROOT` points the vault, seed, and children at another directory. Leave it unset to use the repository that contains `nomo.py`.

## The pieces, in plain words

**Ollama Llama.** The chat models are ordinary local GGUF weights. `llama3.2` is the small router. `llama3.1:8b` is the writer. Their bytes are the bytes Ollama published for those tags.

**Needle 3.** Cactus Compute's on-device tool caller (`import needle`, `generation=3`). The published weights are 2-bit packed, which is the ternary-style layer in this program. Needle routes a tool. It does not write the chat reply. Telemetry is turned off with `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1` before the import. One development run, after the weight download, routed `vault_search` at confidence 0.80, about 176 tokens/s, and 132 MB peak RAM. Treat that as a measurement from one machine, not a quota.

**Journal.** The `jev-` prefix is this file format. Hosted TypeSafe Jev (`jev-1.14.0`, Choice / Noul / Score) is a different system. This program does not call it and does not ship its weights. `choose` asks the local route model for JSON `{choice, score, because}` and stores `calibrated: false`.

**Dream-RSI.** `dream` reads the journal and writes `vault/dreams/<stamp>-dream.md` plus one line in `vault/dreams/PROPOSALS.md`. The next run reads those files. That is the recursion. The pass leaves the Python source alone.

**Parallel.** Three notes run on the route model: scout, critic, builder. The reason model merges them and keeps a step only when one of the notes wrote it. On a single GPU, Ollama queues the three calls.

**Replication.** `replicate scout` copies the code and the seed into `children/scout`, writes `PARENT.txt`, and returns. The child is a separate folder with its own empty vault. Start it yourself with `python nomo.py` from that folder.

**Operator run.** `run` executes one argv in the repository root with `shell` off, a 60 second cap, and a denylist that blocks `git push`, disk-format style commands, and recursive deletes. It stays inert until that process has `NOMO_ALLOW_RUN=1`. The model tool list does not include it. The denylist is a guardrail for obvious forms, not a sandbox.

**Skills.** `seed/skills/*.md` are the nodules: memory, dream, tools, replicate. They are notes the vault can hold, not plugins that execute themselves. `status` lists the skill filenames.

## Layout

```text
nomo.py                 command line, no install required
pyproject.toml          optional `pip install -e .`
nomo/                   agent, model selection, vault, journal, dream, replicate
seed/                   first-run vault pages
modelfiles/             optional Ollama aliases
tests/                  unit tests that do not need a daemon
requirements.txt        optional cactus-needle pin
.env.example            overrides
vault/                  created on first run, not committed
children/               created by replicate, not committed
.venv/                  created by setup --with-needle, not committed
```

Run the tests from the repository:

```bash
python -m unittest discover -s tests -v
```

The tests check model selection, the vault path jail, the run denylist, and that the published tree carries no machine-specific identity.

## Limits

The agent can read and write notes, record peer conclusions, check its journal, list and read files inside the clone, run a three-way parallel pass, record a local choice, and write a dream. `replicate` and `run` wait for the operator.

A small model will be wrong. The journal is the record of what the process did. `status` shows the model name that was actually selected, including the case where the public default was missing and another local model was used.
