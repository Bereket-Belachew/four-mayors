# Demo script (3 minutes) — fill real output before Sunday 11:30

Beats:
1. **Thesis, 15s.** "Same city, same model, same seed. Four mayors that differ only in how they close the loop. Watch which city grows."
2. **Four cities diverge, 45s.** Replay page, seed S, term 2, speed 6. Point at horses vs traffic, shuttered vs open.
3. **Caesar repeats the mistake, 30s.** Scrub term 0 vs term 2: same blunder, same year. "He carries nothing."
4. **Reformer self-catch, 45s.** Lessons panel: rule turns red at end of term 1. Open the Weave trace: memory_write -> checked -> failed, before/after confidence. "The loop caught its own mistake."
5. **Numbers with spread, 30s.** marimo table: min/median/max per mayor, n seeds. Say plainly if ranges overlap. Show the shuffled control.
6. **What we'd do next, 15s.** Human mayor mode; consultant trust as a learned weight.

Fallback if the network dies: `open web/index.html` reads the committed runs; the Weave screenshots live in docs/screens/.

## Commands (paste real output under each)
```
python -m pytest -q
```
```
python runner.py --mayors caesar reformer --seeds 1 --terms 2 --no-weave
```
