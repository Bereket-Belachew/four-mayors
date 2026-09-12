# Round 2 — persistent terms, redesigned lessons (Sat 15:35)
Caesar + Reformer, 3 terms each, unemployment (seed 0) and smog (seed 1), park absorb on, land off, GPT 5.6 Luna.

## Self-catches: 3 (first ever)
- Reformer/unemployment term 1: "with little fiscal cushion, tax consistency precedes new projects" — applied; treasury>=100 by y3 measured FALSE -> 0.78->0.48. Re-tested term 2 -> TRUE -> 0.73. A lesson failed, survived, and recovered.
- Reformer/unemployment term 2: "don't expand industry while pollution elevated" — applied; pollution<=25 by y5 FALSE -> 0.84->0.54.
- Reformer/smog term 1: "don't fund services again until treasury recovers" — applied; debt<=500 by y6 FALSE -> 0.86->0.56.

## Lessons are strategic now
"If debt is high and cash thin, do not borrow again." "Resolve the employment bottleneck before amenities in a city with excess housing." "If population >= 80% of housing and jobs - population >= 200, add housing in the first few years." All carry a variable/comparator/value/year.

## Scores (n=1 per cell; noise-level, behavior is the evidence)
| mayor | city | t0 | t1 | t2 | debt t0->t2 |
|---|---|---|---|---|---|
| caesar | unemployment | 38.4 | 41.0 | 43.9 | 4800 -> 6100 (kept borrowing) |
| reformer | unemployment | 41.4 | 40.8 | 47.8 | 2600 -> 2600 (stopped) |
| caesar | smog | 39.7 | 42.9 | 38.6 | 2200 -> 3100 |
| reformer | smog | 43.1 | 43.4 | 40.6 | 1000 -> 1000; hoarded 20,651 treasury, built 52 parks |

## Flaws surfaced
1. 52 parks in one city: land is not on. Enable land (81 lots) — this is what stops it.
2. Hoarding: fiscal 9 for sitting on 20k while pollution rose 28->45 and happiness sat at 64. Hoarding penalty only fires when services < 20. Should fire on large surplus + any declining criterion.
3. Memory full at 7 rejects good new lessons; replace lowest-confidence instead.
4. Caesar's parks keep climbing (11->26, 10->30): absorb mode makes them weak, he keeps buying. That is his character, and it is legible.
