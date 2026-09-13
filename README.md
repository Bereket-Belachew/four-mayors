# Four Mayors
<img width="1503" height="842" alt="image" src="https://github.com/user-attachments/assets/0db52db1-43c9-467c-8dcc-e19c5c27683f" />

<img width="1960" height="728" alt="image" src="https://github.com/user-attachments/assets/1f5c72fb-e3c4-47f3-83ae-ae1234fec31c" />

<img width="2078" height="1350" alt="image" src="https://github.com/user-attachments/assets/4558b712-5b63-4f92-a84b-7186232b3617" />
<img width="2763" height="1399" alt="image" src="https://github.com/user-attachments/assets/9acd6a6f-8ffe-4f82-a4b9-0c5627f8f190" />



**Same city, same model, same seed. Four mayors that differ only in how they close the loop. Watch which city grows.**

Built solo at CoreWeave Hacks, San Francisco, 2026-09-12/13.

> GIF and Weave links land here Sunday morning.

## The experiment

A deterministic city (seven numbers, eight levers, a 20-year term of office) is governed by an LLM mayor.
The **inner loop** (year by year: see the city, act) is identical for every mayor. The **outer loop**
(what carries from one term to the next) is the only thing that differs:

| Mayor | Carries between terms | Checked against | Failure mode / edge |
|---|---|---|---|
| Caesar | nothing | — | repeats the same mistakes every term (control) |
| The Bureaucrat | every consultation, referendum and report, verbatim, forever | never | drowns in contradictory advice |
| The Reformer | ≤7 lessons distilled from the world's cause-tagged outcomes | the next term's outcomes: wrong lessons lose confidence or die | learns, and can drop a consultant who was wrong twice |
| The Populist | the Reformer's mechanism, plus what citizens said | citizen approval ~2:1 over outcomes | avoids revolt, blind to slow damage |

A **hidden rubric** scores every term. The mayors never see it: a test asserts no rubric phrase appears in any
mayor prompt, and the mayor package has no import path to the judge. The LLM judge (a different lab's model from
the mayors) is reported beside a deterministic scoreboard and never summed into it.

## Run it

```bash
uv venv .venv && source .venv/bin/activate && uv pip install -e .   # or: uv pip install weave openai anthropic pyyaml python-dotenv marimo pytest
cp .env.example .env    # add keys; MAYOR_PROVIDER=mock runs everything with no keys
python -m pytest -q     # 14 tests: determinism, no-crash, cause tags, trap, leak guard, anti-vacuity
python runner.py --seeds 3 --terms 3 --controls --shuffled --judge   # -> runs/runs.jsonl, runs/selfcatch.json
python3 -m http.server 8765 &  open http://localhost:8765/web/         # replay the four cities
marimo edit analysis/compare.py                                        # compare loops across seeds
```

## What we did not build, and why

- **A human mayor mode.** Deferred; it is a second product. The sim is pure, so it is a form away.
- **Talk-to-the-butcher NPCs.** Cut. The economy is embodied instead: horses replace cars, shops shutter, the sky yellows.
- **Weight updates.** None. All learning is in-context, memory-mediated, and measured across seeds. We say so.

## Stack

W&B Weave (every year, memory read/write, both judge calls are traced ops) · TypeSafe AI System One (`jev-latest`) as the second judge: the six rubric criteria as scored questions with legends, answered with calibrated confidence · marimo (analysis) ·
OpenAI GPT 5.6 Luna for the mayors, Claude Sonnet 5 for the first judge · plain Python, no framework · static HTML replay + a small local server for talk-to-a-citizen, run-from-web and narration.
