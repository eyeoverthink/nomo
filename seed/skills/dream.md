# Dream-RSI

`python nomo.py dream "goal"` runs one local Dream-RSI cycle.

The method is Zheng et al., Dream-RSI: Recursive Self-Improvement through Evolving Worlds, arXiv:2609.14858 (2026). The paper and the research code are here:

- https://github.com/zhengkid/Dream-RSI
- https://github.com/google-research/dream-rsi

Online exploration writes a small tree under `vault/dreams/worlds/iterNNN/raw_scores.json`. Each node is one attempt and one score. Offline dreaming replays three policies on those saved scores: `parallel_refine`, `best_first`, and `wide`. The replay does not call the model again. The policy with the higher reward is written to `vault/dreams/policy.json`. A tie keeps the incumbent.

The grid defaults to 2 branches and 1 refinement. Caps are 4 branches, 2 refinements, and 3 rounds. `python nomo.py watch --max N` repeats the cycle at most 24 times and then exits.

The paper scores candidate programs by running them. This clone scores a written attempt from 0 to 1 with the local model, then treats that number as the frozen outcome. The promoted object is a named policy. The cycle leaves `nomo/*.py` untouched.
