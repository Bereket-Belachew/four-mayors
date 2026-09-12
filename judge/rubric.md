# Hidden rubric

The mayors never see this file. A test asserts that no phrase from it appears in any
mayor prompt, and `mayors/` has no import path to `judge/`.

Score each criterion 0-10 from the trajectory (all years), not only the end state.

1. **Prosperity** — jobs relative to population at the end, and the trend. A city where
   most working-age people have work scores high. A jobs collapse late in the term scores low
   even if the start was strong.
2. **Housing adequacy** — housing units per person stayed near 1.0-1.2 for most of the term.
   Chronic overcrowding (below 0.9) or wasteful overbuilding (above 1.5) both lose points.
3. **Fiscal health** — treasury trend and debt. Ending deeply negative, or borrowing without
   the borrowed money producing jobs or housing, scores low. Hoarding a large surplus while
   services decay also loses points.
4. **Environment** — pollution trend. Rising pollution scores low. Reversing a rise scores high.
5. **Wellbeing** — happiness mean across the term and its minimum. One deep dip costs more
   than a mild steady level.
6. **Resilience** — did the city recover from any dip in jobs, treasury, or happiness? Was
   an early exit (bankruptcy, depopulation, revolt) avoided? A term that ended early scores
   0-2 here regardless of other numbers.

Return per-criterion scores and a one-paragraph verdict naming the single decision that
mattered most, with its year.
