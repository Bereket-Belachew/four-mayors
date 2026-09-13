# How the city works, in plain words

This is every rule the world runs on, every number in those rules, and why I picked it.
I picked all of them alone on Saturday afternoon. None have been checked by anyone.
Read this to find the errors. Each number has a name in brackets, like [park_cleans],
so that when you change your mind the code changes in one place.

**Where the rules live today:** `sim/world.py` (the city), `judge/scoreboard.py` (the formula
grader), `judge/rubric.md` (the prose the LLM grader reads), `mayors/memory.py` (how lessons
are checked). The numbers are still spread through those files. The first coding ticket after
you approve this document is to pull every named number into one file, `sim/params.py`, so
your research can change the math without touching logic.

---

## What I already know is wrong or fragile

Found by running 4,000 random action scripts through the world before any model touched it.

1. **Doing nothing scores the same as a typical random mayor** (31.8 vs 33.9 of 60). Most
   actions cost more than they return. A city left alone neither grows nor collapses.
2. **Nine parks drive pollution to zero.** The environment grade is trivially maxed by park spam.
3. **Seeds barely change anything.** The same script scores 55.3 to 55.5 across five seeds.
   All the randomness we will see comes from the model, not the world.
4. **Debt can never be repaid.** Borrowing is a one-way ratchet at 8% a year.
5. **The consultants' forecasts use an old version of the upkeep rule**, so they are wrong beyond
   the bias we designed. Fix: forecast by actually simulating one quiet year, then apply the bias.
6. **Consultation results arrive a year late.** Ask in year 5, read in year 6. This is a design
   choice, not an accident, but probably the wrong one.
7. **A blind search reached 55.5 of 60.** If a capable model finds the same recipe in its first
   term, all four mayors hit the ceiling and the loops stop mattering.

---

## 1. The city is seven numbers

Picture a town of a thousand people. The world keeps track of exactly seven things about it.

| Number | Starts at | Plain meaning | Range |
|---|---|---|---|
| population | 1000 | how many people live here | 0 and up |
| housing | 1100 | how many people *could* live here (one unit = one person) | 0 and up |
| jobs | 900 | how many people *could* work here | 0 and up |
| treasury | 500 | the city's money. Can go below zero | any |
| pollution | 20 | how dirty the air is | 0 to 100 |
| happiness | 60 | how content people are | 0 to 100 |
| services | 50 | how well schools, clinics, police work | 0 to 100 |

Why these starts: a thousand people so percentages are easy to read; slightly more housing than
people so there is room to grow; fewer jobs than people so there is a mild problem to solve on
day one. Nothing deeper than that.

The world also keeps a few bookkeeping numbers a citizen would not name: the tax rate (starts at
15%), the transit level (starts at 1 of 3), how many factories (3) and parks (2) exist, how much
debt is owed (0), and how many years in a row the city has been very unhappy or very broke.

**Derived, never stored.** Some things are computed from the seven when needed:
- The **workforce** is 60% of the population [workforce_share]. Assumption: children and elderly
  make up the other 40%.
- **Employment rate** is jobs divided by workforce, capped at 100%. **Unemployment** is the rest.
- **Housing ratio** is housing divided by population. 1.0 means exactly enough homes.
- **Economy tier** (0 to 3) is only for the picture: it decides horses versus cars, shuttered
  versus open shops. It weighs employment, treasury, and happiness.

---

## 2. A year, in order

Every year happens in the same six steps, in this order. Order matters because money spent in
step 3 is not there for interest in step 5.

1. The mayor's actions are checked. Unknown or malformed ones are ignored and logged, never crash.
   Only the first three valid ones count [max_actions_per_year = 3].
2. Information actions run (consultations, referendum, reading the report). They charge a fee and
   change nothing about the city.
3. Levers are paid for now. Their effects go into a **pending queue** with the year they land.
4. Pending effects whose year has come land now, each tagged with the decision that caused it.
5. The economy turns: money, pollution, services, jobs, happiness, population, in that order.
6. The world checks whether the term has ended.

---

## 3. The eight levers

A lever is something a mayor does to the city. Every mayor, including a human, has all eight.

| Lever | Costs now | Lands | Then, every year after |
|---|---|---|---|
| set tax (0 to 40%) | nothing | same year | revenue changes (see §4). Above 30% [tax_flight_threshold], 2% of jobs leave each year [tax_flight_rate]. Happiness target falls by 60 × rate [tax_unhappiness]. |
| build housing (10 to 400 units) | 1.5 per unit [housing_cost] | next year | units appear. People move in over time (§4). Jobs do not change. |
| build factory (1 to 3) | 300 each [factory_cost] | in 2 years | +150 jobs each [factory_jobs]. +2 pollution per year each, forever [factory_smoke]. +20 upkeep per year each [factory_upkeep]. |
| build park (1 to 3) | 120 each [park_cost] | next year | −1.5 pollution per year each, forever [park_cleans]. |
| fund transit (level 0 to 3) | 150 per level [transit_cost] | in 2 years | −1 pollution per year per level [transit_cleans]. +40 upkeep per year per level [transit_upkeep]. |
| fund services (level 0 to 3) | 200 per level [services_cost] | same year | +12 services points per level [services_gain]. |
| subsidize business (1 to 5) | 100 each [subsidy_cost] | next year | +40 permanent jobs each [subsidy_jobs]. |
| borrow (100 to 2000) | nothing | same year | cash now, debt forever, 8% interest a year [interest_rate]. **No repay lever exists.** |

Why the delays: housing and parks take a year to build, factories and transit take two. This is
what makes "the fuse" visible in the game: a decision whose consequence has not landed yet.

Why factories are the big lever: 150 jobs for 300 money is the best jobs-per-money in the game,
on purpose, so the industrialist's advice is tempting. The price is permanent smoke and upkeep.

---

## 4. The economy turns (the drift rules)

These run every year whether or not the mayor did anything. Each is one sentence of intent, then
the current formula.

**Money in.** Each *filled* job pays tax; a vacancy pays nothing [tax_filled_jobs_only]. Revenue = tax rate × min(jobs, workforce) × 5.5 [wage].
The workforce is 60% of the people [workforce_share], which is real (the US rate is 62%). The starting city has 540 jobs for 600 workers,
so 10% are idle and revenue is 446 a year against about 410 of upkeep: a little slack, not a fortune. Fill the jobs and it is 495.
(Changed 2026-09-13: the old world taxed all 900 jobs on 600 workers, so half the revenue was phantom and one mayor banked 78,000.)

**Money out.** Running a city costs 0.25 per resident [upkeep_per_head], 40 per transit level,
20 per factory, and 60 × services/50 for services [services_upkeep]. At the start that is about
410. So the starting city roughly breaks even. This was tuned so that doing nothing is neither
a win nor a collapse.

**Interest.** 8% of the debt is paid every year, forever.

**Pollution.** Goes up 2 per factory, down 1.5 per park, down 1 per transit level, plus a little
noise (±1) [pollution_noise]. Three factories and two parks and one transit line: +2 a year.
So the starting city slowly dirties. **Known flaw:** there is no floor from population itself,
so enough parks reach zero.

**Services decay.** Minus 4 points a year, always [services_decay]. Schools and clinics need
funding to stay good. Unfunded, the starting 50 hits zero in 12 years.

**Jobs leave, and arrive, with the tax rate.** Business drifts 10% of the way each year toward jobs × (15% ÷ rate)^0.3 [tax_flight_mode = slope,
tax_reference, tax_elasticity, tax_drift]. At 30% tax jobs settle 19% below par; at 40%, 26%; at 5% they grow, but at most 30% above par [tax_pull_cap].
This is Bartik's finding (1992): tax competition is a gentle slope, not a cliff. If services are below 20, 1% of jobs close a year [services_flight_rate].
**Jobs no one can fill do not last:** jobs above 1.1 × the workforce shrink by 10% of the excess each year [labour_ceiling, unfilled_shrink_rate].
**Once a term there is a recession:** in a year drawn from the seed between 5 and 15, 10% of jobs vanish [shock_enabled, shock_year_range, shock_jobs_drop].
Every mayor gets exactly one; the Reformer can learn that it comes but not when.
**Homes wear out:** 1% of housing falls out of use each year [housing_depreciation], so a stagnant city slowly loses homes (Glaeser & Gyourko 2005).

**Happiness.** People have a target level of contentment given their situation, and each year
happiness moves halfway toward it [happiness_inertia = 0.5], with ±2 noise. The target is:

    45 [base]
    + 30 × employment rate            (having work matters most)
    + 15 × housing ratio, clamped 0.8..1.2, minus 15   (enough homes, not too crowded)
    − 0.35 × pollution                (dirty air hurts)
    − 60 × tax rate × (1 − services/100)   (taxes hurt only as far as they fail to buy services: 15% with services at 50 costs 4.5 points; Oishi et al. 2012)
    + 0.25 × services                 (good services help: 50 points gives 12.5)

So a fully employed, well-housed, clean, low-tax, well-served city tops out near 100.

**Population.** People arrive and leave.
- Arrivals: half of the empty homes fill each year [move_in_rate], scaled by how happy the
  city is (from 0.5× at zero happiness to 1× at 100).
- Departures: each year the city loses 8% × the unemployed share of people [unemployment_exodus],
  plus 0.2% × (pollution above the starting 20) [pollution_exodus, pollution_baseline] (people leave over air getting worse, not over air as it is: Chen, Oliva & Zhang 2017),
  plus 3% if happiness is below 35 [misery_exodus].
- If there are more people than homes, half the excess leaves [overcrowding_exodus].

**This is where the housing trap lives.** Build 400 units a year and people pour in, jobs do not
follow, unemployment climbs, and departures plus construction costs bankrupt the city around
year 7 with population still near its peak. It looks like success right up to the end.

---

## 5. How a term ends

A term is 20 years [horizon]. It ends early if:
- **Bankruptcy:** treasury below −3000 [bankruptcy_floor] for 2 years running. The day it happens, happiness falls 25 points
  [bankruptcy_mood_shock]: wages unpaid, pensions cut, the city's credit gone (Detroit 2013). The next term inherits that misery.
- **Depopulation:** population below 20% of where it started [depopulation_share].
- **Revolt:** happiness below 25 [revolt_floor] for 3 years running [revolt_years].

Why these: bankruptcy needs a grace year so one bad year is survivable; revolt needs three so a
dip is not a coup. The specific numbers are guesses.

---

## 6. Information actions and what they return

These are the "loop actions". They tell the mayor something; they change nothing about the city
except the fee. **Their results are computed by the world, deterministically. The model only reads
them.** That is what keeps the world a pure function even with advisors in it.

**Consult the industrialist** (fee 30). A one-year forecast of jobs, pollution, treasury, and
happiness, then a bias: jobs ×1.25, pollution ×0.6 [industrialist_bias]. Plus a fixed line:
"Build factories. Jobs are the only thing that matters; smoke is the smell of money."

**Consult the economist** (fee 30). The same base forecast, then: treasury ×1.15, and the
happiness line is deleted [economist_bias]. Fixed line: "Raise taxes and cut services. A balanced
budget cures everything."

Why two biased advisors: so the Bureaucrat's records contradict each other with no way to tell
who was right, and so the Reformer can *discover* who was right from outcomes.

**Known flaw:** the base forecast uses an upkeep formula I later changed, so both advisors are
wrong by more than their bias. Fix: simulate one quiet year on a copy and use that as the base.

**Hold a referendum** (fee 60) on a proposed lever. Returns approval percent = current happiness
+ a fixed popularity of the lever [popularity: tax −25, housing +10, factory +5, park +15,
transit +8, services +12, subsidy −5, borrow 0] + noise ±8. Also a turnout figure.

**Read last year's report** (free). Every change last year with the decision that caused it.

**Timing (design choice to revisit):** results are shown to the mayor the *following* year.

---

## 7. What the graders do

Two graders look at a finished term. Neither is ever shown to a mayor.

### The formula grader (scoreboard)

Six criteria, each 0 to 10, total 60. Written as formulas so the same term always scores the same.

| Criterion | Intent | Current formula, roughly |
|---|---|---|
| prosperity | most working-age people have work, and jobs did not collapse | employment rate × 8, plus up to ±2 for the jobs trend |
| housing | homes stayed near "just enough" | 10 × average credit, where a year earns full credit at 1.03–1.10 homes per person (the natural vacancy rate, 3–10% empty) and credit falls straight to zero at 0.9 and 1.5; minus 5 × share of years outside 0.9–1.5. No free points. |
| fiscal | money got better, debt was useful, no hoarding | 5 + treasury change in thousands (capped ±4); −3 if ending below −1000; −2 if borrowed and nothing grew; −2 if sitting on 3000+ while services under 20 |
| environment | air got cleaner | 6 − (pollution change)/6 |
| wellbeing | people were content, no deep misery | 0.7 × average happiness/10 + 0.3 × lowest happiness/10 |
| resilience | climbed back fast from the recession and other dips; no early exit | early exit: at most 2. Otherwise 7 − 0.5 per year spent in a dip + 1.5 per recovery (dip = 15% below the running peak in jobs or happiness; recovery = back to 95%). Treasury is not counted: spending it is a choice, not a shock. |

**A term that ends early keeps only the share of its marks it survived:** every criterion is multiplied by years played ÷ 20, so a
bankruptcy in year 7 keeps 35% and a two-year stub keeps 10%. Happy citizens in year 6 do not redeem a default in year 7
(added 2026-09-13 11:20, his call: bankruptcies were scoring within a few points of full terms).

Every weight here is my judgement of what a good mayor is. Change any of them.

### The reading grader (LLM judge)

A different lab's model (Claude) reads six paragraphs of prose saying the same six things, plus
one line per year of the term, and returns a 0 to 10 per criterion and a paragraph naming the
decision that mattered most. **Nobody decided that a given city is worth 89.** The model read
prose and produced a number. That is why its score is shown next to the formula grader's and is
never added to it, and never enters any mayor's memory.

---

## 8. How a lesson is checked (the Reformer and the Populist)

At the end of a term, the world hands the mayor a summary: for each lever it pulled, the total
change in each of the seven numbers that the world attributed to that lever, plus the overall trend.

The mayor writes up to 4 new lessons [lessons_per_term], keeping at most 7 [max_lessons]. A lesson
must name a **lever**, a **number**, and a **direction** ("building factories pushes pollution up").
That is what makes it checkable.

At the end of the *next* term, each lesson is compared with what that lever actually did:
- Right: confidence +0.25 [lesson_reward], seen +1.
- Wrong: confidence −0.30 [lesson_penalty]. Below 0.2 [lesson_floor], the lesson is deleted.
- Lever not pulled this term: untested, kept as is.

**The Populist's twist.** The verdict is blended two parts citizen approval to one part outcome
[approval_weight = 2], except for the two most confident lessons [anchored_slots], which are
checked on outcomes only. Approval is computed from the happiness trend over the term.

**Caesar** writes nothing. **The Bureaucrat** appends every consultation and referendum result
to a log that is never checked against anything.

---

## 9. Added 2026-09-12 ~15:00, after the first real run

**Every number now lives in `sim/params.py`**, under the bracketed names used above. Change it
there. Rules that change behavior are behind flags so a change can be compared against the old
behavior on the same seed.

### Hard starts: each seed opens on a different problem [SCENARIOS]

| Seed | Scenario | What is wrong on day one |
|---|---|---|
| 0 | unemployment | only 420 jobs for a workforce of 600 (30% idle), happiness 48, treasury 400 |
| 1 | smog | pollution 70, six factories and no parks, 1300 jobs, happiness 45 |
| 2 | debt | 2500 owed, treasury −800, services 30 |
| 3 | housing shortage | 550 homes for 1000 people, happiness 42 |

Left alone: the unemployment city ends 2800 in the red, the smog city hits pollution 100 and
happiness 33, the debt city goes bankrupt in year 15, the shortage city loses half its people.
Each is a real problem with a different first move. A lesson learned on one is tested on another.

### Land is finite [land_enabled, off by default until confirmed]

The city has 81 lots [lots_total]: the 12 by 12 grid minus roads. A factory takes 2
[lots_per_factory], a park 1 [lots_per_park], every 100 housing units 1 [lots_per_100_housing].
Lots are reserved the year a build is ordered so two orders cannot claim the same land. When
lots run out, a build is refused and logged. Two new levers appear: **demolish** (factory, park,
or 100 housing; a demolished factory takes its 150 jobs with it) and **buy land** (400 per lot
[buy_land_cost], up to 10 a year). The picture on screen is now literally the land.

**Open question for you:** at 81 lots, money ran out before land did in a factory-spam test
(15 factories, 26 lots still free). If land should bite, 60 lots is the number to try.

### Trees cannot cancel smoke one for one [park_mode = "absorb"]

Old rule: each park subtracts a fixed 1.5 pollution a year, so nine parks beat any number of
factories and pollution hits zero. New rule: factories emit 2 each [factory_smoke], people emit
1 per thousand [population_smoke], and parks absorb a **share** of whatever is in the air: the
first park 12% [park_absorb_first], each additional park 80% of the previous one's share
[park_absorb_decay]. Nine parks absorb about 45% of ambient pollution a year, never all of it.
Test: eleven parks against three factories now settle at pollution 10.6 instead of 0.

### Consultants forecast honestly, then lie [forecast_mode = "simulate"]

The base forecast is now a real simulation of one quiet year on a copy of the city, so it is
exactly as wrong as the consultant's bias and no more. The fee (30) is charged before the
forecast, so the treasury line is 30 lower than a free forecast would be. Old naive formula
kept behind `forecast_mode = "naive"`.

### The city persists across terms [decided 2026-09-12 ~15:30]

Term two starts where term one ended: population, homes, jobs, treasury, debt, pollution,
happiness, services, factories, parks, land. The year counter resets, and so do the "years in
a row unhappy/broke" streaks, so a new term is not deposed on day one for the old term's misery.
Noise is re-seeded per term. Consequence: "same seed" holds only at term one; after that the four
cities differ because of what each mayor did, which is the point. Borrowing now hurts in the
city, not only on paper. The fiscal grade also now scores **net worth** (treasury minus debt).

### Lessons, redesigned [same time]

The first real run produced lessons like "funding services raises services," true and unfalsifiable.
A lesson is now: **when** the city looks like X, **do/avoid** Y, and **expect** variable V to be
on one side of a value by year N. The post-mortem prompt forbids restating what a lever does.
At the end of the next term, the model reviews each lesson against the year-by-year record and
says whether it applied the strategy and whether the record supports it, quoting the evidence.
Where the lesson has a measurable prediction and was applied, the prediction is checked by code
and overrides the model's verdict. Confidence arithmetic stays in code. Lessons with no
measurable prediction are rejected at write time.

### Balance call I made alone [wage 3.0 -> 3.5, services_cost 200 -> 150, 2026-09-12 ~15:50]

With land and absorption on, a mayor who funded services every third year and built a park now
and then ended 1,590 in the red and scored below doing nothing. Revenue (405) equalled upkeep
(410), so every spend was a deficit. I raised the taxable wage to 3.5 (revenue 472, about 60 a
year of slack) and cut services to 150 per level. Revert or change in `sim/params.py` if you
disagree; the test `test_do_nothing_scores_below_a_reasonable_mayor` is the guard.

### Citizens live the debt [decided 2026-09-12 ~19:20, his call]

Before this, debt had one channel into the world: interest drained the treasury, and nothing
connected the treasury to daily life until bankruptcy ended the term. A city 26,000 in debt
had services at 84 and happiness at 70. Four rules fix that, all in `sim/params.py`:

- **Austerity.** While the treasury is negative, services decay an extra 2 points a year per
  1,000 of shortfall [austerity_decay_per_1000], capped at 8 [austerity_decay_cap]. The city
  cannot pay its teachers. The event says so.
- **Debt weighs on people.** The happiness target falls by 10 × (yearly interest per resident)
  [debt_unhappiness_per_head], and by 3 per 1,000 of negative treasury
  [deficit_unhappiness_per_1000]: unpaid wages, arrears, the mood of a town underwater.
- **Lenders stop lending.** A loan is refused once total debt would exceed 5 years of tax
  revenue [credit_limit_years] or 3,000 [credit_floor], whichever is higher. The refusal is
  logged and the chronicler can stage it.
- **Business leaves an over-indebted city.** 1% of jobs a year while over the limit
  [debt_job_flight_rate].

Test: the same borrow-every-year script with and without these rules; with them, lenders refuse,
austerity events appear, and mean happiness over the term is at least 3 points lower.

---

## What would refute this design

- If a real model finds the parks-plus-factories recipe in its first term, the ceiling is too
  close and all four mayors converge. The fix is a harder world, not a smarter mayor.
- If the Bureaucrat and the Reformer land in the same place after three terms, the memory
  policies are stylistic after all. Dials: log size, consultant bias size, lesson cap.
- If lessons come back vague (no lever, number, direction), nothing is ever falsified and the
  self-catch moment never appears. The post-mortem prompt forces the shape; untested.
- If seeds keep scoring within 0.2 of each other, "across seeds" is not evidence of anything.
  Seeds should vary the starting city.

## What only running it can settle

How often a real model's lessons are testable. Whether any lesson ever fails. Whether the
Populist's approval blend produces different behavior or just different confidence numbers.
Whether the housing trap ever tempts a model. All of this is unknown until the first real run.


## 10. Grounded in the literature [2026-09-13 morning, his go after the research]

`docs/research/world-models.md` compares every rule above with 55 years of city models and the wellbeing research,
in plain words with sources. These are the changes it produced. Each is one rule, applied to all four mayors alike.

| What changed | Old | New | Copied from |
|---|---|---|---|
| Who pays tax | every job, filled or not | only jobs someone holds | how towns actually tax (income and property, never vacancies) |
| Starting jobs | 900 for 600 workers | 540 for 600 workers (10% idle) | SimCity manual, Cities: Skylines demand rule; the Beveridge curve |
| Jobs no one can fill | stayed forever | shrink 10% of the excess a year above 1.1 × workforce | tight labour markets |
| Tax flight | nothing below 30%, 2%/yr cliff above | a slope: jobs settle at (15%/rate)^0.3 of par | Bartik 1992 (elasticity −0.1 to −0.5) |
| Tax and mood | 60 × rate, always | 60 × rate × (1 − services/100) | Oishi, Schimmack & Diener 2012 |
| People leaving over smog | 0.2% × pollution level | 0.2% × pollution above 20 | Chen, Oliva & Zhang 2017 (they measure changes) |
| Homes | never decay | wear out 1% a year | Glaeser & Gyourko 2005 |
| Housing score | band 1.0–1.2 plus a free 2 | band 1.03–1.10, credit tapering to the bad edges, no free points | Rosen & Smith 1983 natural vacancy |
| Resilience | 7 ± 1.5 per dip/recovery, nothing to recover from | one seeded recession a term (−10% jobs, year 5–15); 7 − 0.5 per year in a dip + 1.5 per recovery | Martin & Sunley 2015 |
| Wage constant | 3.5 | 5.5 | balance: full employment at 15% must cover upkeep and one service level every three years |

**Kept on purpose, and labelled:** parks still absorb 12% of ambient pollution (real trees: under 1%, Nowak 2014). A park that does
nothing measurable is not a lever a 20-year game can use. **Not changed, on the evidence:** the debt penalty on mood stays small;
the research does not support a large direct effect of public debt on wellbeing. Debt hurts through austerity, which is Detroit's story
and already in the rules.

Baselines under the new rules (seed 0, default city, formula score of 60): do nothing 32.5 · a modest active mayor (subsidies, services) 41.5 ·
the housing trap 18.4 (bankrupt year 7) · a borrowed factory town 23.2 · 40% tax 30.3 · 5% tax bankrupt in year 18 ·
the best of 400 random scripts 43.2. Doing nothing is no longer a good mayor.
