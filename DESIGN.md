# CoreWeave Hacks 2026-09-12 — design notes (living draft, for critique)

## Thesis
Same city, same model, same seed. Mayors differ in exactly one thing: how they close
the loop. Watch which city grows. Then: are *you* a better mayor than them?

## The four AI mayors (loop is the variable, ideology is the costume)
| Mayor | Loop design | Learns between terms |
|---|---|---|
| The Dictator | No memory | Nothing. Repeats mistakes. Control arm. |
| The Bureaucrat | Raw log | Everything verbatim. Context bloats. |
| The Reformer | Reflection | 3 lessons from metrics after each term. |
| The Populist | Reflection + citizens | Same, plus NPC interviews folded in. |

## Rules carried over from the Fana brain
- Hidden rubric. LLM judge = scoreboard only. Judge output NEVER enters any mayor's context.
- Mayors see only the city (treasury, jobs, housing, pollution, happiness) and citizen speech.
- Several seeds per mayor; show variance, not one run.
- One deliberately gameable metric (housing spam) so self-deception is visible on screen.
- Deterministic sim, seeded, pure function. Reproducible traces.

## Human mayor (added 2026-09-12)
Anyone at the event opens the URL and plays a city, turn-based, own pace. Scored on the
same hidden rubric after N terms. Leaderboard places them among the AI mayors' score
distributions. Human = fifth loop design.

## Pacing: decision -> consequence must be felt
Two clocks. Decide (3s card) -> term plays out as animation (~6s: tiles upgrade/decay,
vehicles change, headline ticker) -> scoreboard tick (1s). ~10s per term, 20 terms ~3-4 min.
- Every visible change is cause-tagged: hover a decayed building -> "because: tax hike, term 3".
- Real lag: some consequences land 1-2 terms later and show as "pending consequences: 2".

## "Open world" = clickable, not walkable
State -> sprite lookup: economy tier drives vehicle set (cars vs horses), shop open/closed,
crowd density, sky tint. Click a building -> talk to its NPC (prompt over a state slice +
mayor's recent decisions). Job board building -> real openings from the sim. No character
controller. Same NPC layer is the Populist's feedback channel.

## Build order (cut from the bottom)
1. Deterministic sim (6-7 state vars, ~8 actions/term). 2. One mayor loop, Weave-traced,
then clone into 4. Weave Evaluations for the rubric. 3. Flat tile-grid renderer.
4. Four cities side by side, scrubbable. 5. Human mayor + leaderboard (client runs sim,
only scores posted). 6. marimo comparison notebook. 7. NPC chat.

## Prizes targeted
Best Loop Design (main), Best Use of Weave, Best Social Media demo, Best Use of marimo.

## Boundary
No Fana accounting world, code, or internal material. Cities are a clean domain.
