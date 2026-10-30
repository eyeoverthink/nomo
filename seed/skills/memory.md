# Memory

Three stores, on purpose:

- Obsidian vault: markdown notes and wikilinks under `vault/`.
- Honcho cards: `vault/peers/`. The operator card is `peers/operator.md`. A conclusion has a confidence and an evidence id. The confidence is a written weight, not a calibrated probability.
- Journal: `vault/journal/events.jsonl`. Each line stores the hash of the previous line. The id prefix `jev-` marks that local chain. It is not the hosted Jev model.

`vault_search` uses keyword overlap, and cosine distance when the embed model has indexed the note.

Every prompt also receives:

- `vault/record.jsonl`, a SHA-256 chain of interactions.
- Hits from the local embedding index.
- Rows from `vault/graph.sqlite`.
- Fossils written by `python nomo.py evolve` after a sandboxed run passes.

`python nomo.py absorb https://example.com/page` stores one public page as a note. Private hosts are refused.
