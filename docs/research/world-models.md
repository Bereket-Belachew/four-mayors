# How our city compares with published city models

*Research note, Sun 2026-09-13. Companion to `docs/WORLD-RULES.md`. Nothing here changes code; every fix is a proposal.*

For 55 years people have been building cities out of a handful of numbers and letting them run. Jay Forrester's *Urban Dynamics* (1969) was the first: nine stocks (three kinds of housing, three ages of business, three classes of people) joined by feedback loops, stepped one year at a time, with people moving in when the city was more "attractive" than its surroundings and leaving when it was less. Its famous result was that a low-cost housing programme made the city worse: housing for 2.5% of the underemployed a year pulled in more poor residents, drove out business, and left a bigger underemployed population with fewer jobs ([Forrester via Jarzynski, System Dynamics Society 2006](https://proceedings.systemdynamics.org/2006/proceed/papers/JARZY255.pdf); [attractiveness principle](https://en.wikipedia.org/wiki/Attractiveness_principle)). Will Wright read that book and built SimCity on it ([Logic Magazine](https://logicmag.io/play/model-metropolis/)). In parallel, economists built the Lowry model (jobs decide where people live, people decide where shops go), Tiebout's "voting with your feet" (people pick the town whose taxes and services suit them), and Roback's wages-and-rents model (a nice place has lower wages and higher rents; the gap is the price of niceness). Since 2020 reinforcement-learning labs have added toy economies too: Salesforce's AI Economist, and gym wrappers around the open-source SimCity engine, Micropolis.

**Verdict in one sentence:** our world has the *shape* of a Forrester model (stocks, delays, feedback, a housing trap) and gets most signs right, but three simplifications the literature would never make — jobs that need no workers, tax on jobs nobody fills, and a debt ceiling low enough that debt never bites — mean our scoreboard cannot distinguish a good mayor from a passive one.

---

## 1. Jobs (our "prosperity")

**What researchers found**
- About 62% of the US population aged 16+ is in the labour force (working or looking); the unemployment rate is the unemployed divided by that labour force, not by the population ([BLS definitions](https://www.bls.gov/cps/definitions.htm); [FRED CIVPART](https://fred.stlouisfed.org/series/CIVPART)).
- When vacancies outnumber the unemployed, the market is "tight": unemployment stops falling, wages rise, and unfilled jobs stay unfilled or relocate. This is the steep end of the Beveridge curve, the plot of vacancies against unemployment ([Wikipedia](https://en.wikipedia.org/wiki/Beveridge_curve)).
- Okun's law: each extra point of unemployment costs roughly 2% of output ([Wikipedia](https://en.wikipedia.org/wiki/Okun%27s_law)). Output, and so tax, falls with idle people, not with empty desks.
- Games agree. The SimCity manual: "If there are more jobs in your city than residents, new settlers will be attracted" and jobs should "roughly equal" residents ([Micropolis manual](https://github.com/danielellis/micropolis/blob/master/micropolis-activity/manual/inside.html)). Cities: Skylines: "Industrial demand is simply a reflection of unemployment," and players keep 5-10% unemployment so factories can find staff ([Skylines wiki](https://skylines.paradoxwikis.com/Zoning); [Steam guide](https://steamcommunity.com/sharedfiles/filedetails/?id=578759936)).

**What our world does**
Workforce = 60% of population `[workforce_share]`. Employment rate = min(1, jobs / workforce). The default city opens with 900 jobs and 600 workers, so employment is 1.0 from year one and stays there in all 24 demo terms. Jobs never need a worker; a job with no one to fill it still pays tax and still counts.

**How far apart**
The 60% share is right (real: 62%). The direction of every job rule is right. The *level* is wrong: 1.5 jobs per worker is a labour shortage no model or game allows to persist, and our world rewards it instead of correcting it. Prosperity is 10/10 for doing nothing.

**The closest simple fix**
`filled_jobs = min(jobs, workforce)`; jobs above 1.1 × workforce shrink 10% a year ("no staff, business leaves") — the Beveridge tight-market rule. Start the default city at 540 jobs (10% unemployment, the Skylines player's target) so there is a problem to solve.

---

## 2. Homes (our "housing adequacy")

**What researchers found**
- Rental markets have a *natural vacancy rate*, the share of empty units at which rents hold steady, about 5-8% ([Rosen & Smith 1983](https://econpapers.repec.org/article/aeaaecrev/v_3a73_3ay_3a1983_3ai_3a4_3ap_3a779-86.htm); [Texas Real Estate Research Center](https://trerc.tamu.edu/article/rent-natural-vacancy-rates/)). Below it rents rise and people crowd; above it rents fall.
- Housing is durable, so decline is slow: when a city loses jobs, prices fall much more than population, and cheap housing then attracts low-income newcomers ([Glaeser & Gyourko 2005](https://www.nber.org/papers/w8598)).
- Forrester's result again: build homes without jobs and you import unemployment. Our "housing trap" is this finding.
- Where people live follows where the jobs are (Lowry 1964, [RAND](https://www.rand.org/pubs/research_memoranda/RM4035.html)) and which tax-service bundle they prefer ([Tiebout 1956](https://escholarship.org/uc/item/9fq454wm)).

**What our world does**
Half the empty homes fill each year, times 0.5 + happiness/200 `[move_in_rate]`. Overcrowding: half the excess people leave `[overcrowding_exodus]`. Mood term: 15 × ratio clamped to 0.8-1.2, minus 15, so the whole range of housing conditions is worth ±3 mood points. Scoring: share of years with ratio in 1.0-1.2, plus a flat +2.

**How far apart**
Same direction throughout, and the trap is Forrester's. Two gaps: the "good" band (0-20% vacancy) is wider than reality's (5-8%) and the +2 means a passive mayor scores 10; and there is no price, so neither shortage nor glut costs anyone anything except a ±3 mood nudge. Glaeser's slow decline is absent: housing never depreciates.

**The closest simple fix**
Score the band 1.03-1.10 (natural vacancy) and drop the +2; let housing depreciate 1% a year so a stagnant city slowly loses homes (Glaeser & Gyourko). Two lines in `scoreboard.py`, one in `world.py`.

---

## 3. Money (our "fiscal health")

**What researchers found**
- Real towns tax property, sales and *earned* income: property tax is about three quarters of local tax revenue, income tax about 6% ([Tax Policy Center](https://taxpolicycenter.org/briefing-book/what-are-sources-revenue-state-and-local-governments)). None of these is paid by a vacant job.
- Tax competition is real but modest. Bartik's review puts the elasticity of business activity to local taxes at roughly −0.1 to −0.5: cut taxes 10% (say 15% to 13.5%) and business grows 1-5% in the long run ([Bartik 1992](https://doi.org/10.1177/089124249200600110)). It is a slope, not a cliff.
- The Laffer curve, in plain words: revenue = rate × base, and the base shrinks as the rate rises, so revenue peaks and then falls. Estimates for the peak run 26-34% for corporate tax and 35-70%+ for top income tax; most places sit below it ([Congressional Research Service](https://www.congress.gov/crs-product/R48913)).
- US cities face constitutional debt ceilings of commonly 5-7% of assessed property value ([NABL](https://www.nabl.org/bond-basics/debt-limit/)). Beyond them comes bankruptcy, which is lived by residents: Detroit filed in 2013 with 40% of streetlights dark, 58-minute police response times, and a population down from 1.85 million to about 700,000, 25% of it lost in 2000-2010 alone ([CNN Money](https://money.cnn.com/2013/07/19/news/economy/detroit-streetlights-police); [Washington Post](http://www.washingtonpost.com/wp-dyn/content/article/2011/03/22/AR2011032202683.html)). Stockton laid off a quarter of its police and set a homicide record; Vallejo's force fell 40% and homicides went from 7 to over 24 a year ([Bridge Michigan](https://bridgemi.com/michigan-government/stockton-vallejo-warn-detroit-you-aint-seen-nothin-yet/)).

**What our world does**
Revenue = tax × jobs × 3.5 `[wage]` on *all* jobs. Above 30% tax, 2% of jobs leave a year `[tax_flight_threshold, tax_flight_rate]`; below it, nothing. Interest 8% `[interest_rate]`, no repay lever. Lenders refuse once debt exceeds max(3000, 5 years of revenue) `[credit_floor, credit_limit_years]`; at the default city that is 3000. While broke: services lose an extra 2 points per 1000 of shortfall, capped at 8 `[austerity_*]`. Bankruptcy at −3000 for two years ends the term.

**How far apart**
The austerity rule is Detroit in miniature and the debt ceiling is roughly the right size (5-7% of property value is a few years of property-tax revenue). The tax base is the wrong thing: 900 taxed jobs on 600 workers is 50% phantom revenue, which is why one mayor ended with 78,000 in the bank. Tax flight is a cliff at 30% where reality is a gentle slope from zero; below 30% our world has no Laffer curve at all, so the top tax rate is always revenue-maximising.

**The closest simple fix**
`revenue = tax × min(jobs, workforce) × wage` (one line, and it also fixes the forecasts). Replace the cliff with Bartik's slope: each year jobs drift 10% of the way toward `jobs × (0.15 / tax)^0.3`. At 30% tax that settles 19% below par; at 40%, 26%.

---

## 4. Air (our "environment")

**What researchers found**
- Trees remove pollution, but little of it. All US trees removed 17.4 million tonnes in 2010, "less than one percent" of ambient concentrations; per city, 0.05% (San Francisco) to 0.24% (Atlanta) ([Nowak et al. 2014](https://www.fs.usda.gov/nrs/pubs/jrnl/2014/nrs_2014_nowak_001.pdf)). The health value is real; the concentration change is tiny.
- Pollution drives people out. In China a 10% rise in air pollution cut a county's population by about 2.8% through net out-migration over five years, led by the young and educated ([Chen, Oliva & Zhang, NBER 2017](https://www.nber.org/papers/w24036)).
- SimCity: industry "is the primary cause of pollution"; pollution lowers land value, which raises crime, which lowers land value ([Micropolis manual](https://github.com/danielellis/micropolis/blob/master/micropolis-activity/manual/inside.html)).

**What our world does**
+2 per factory a year `[factory_smoke]`, +1 per 1000 people `[population_smoke]`. Parks absorb a share of ambient pollution: 12% for the first, each next park 80% of the previous `[park_absorb_first, park_absorb_decay]`; nine parks about 45%. Transit −1 per level. Exodus 0.2% of population × pollution `[pollution_exodus]`: at the starting 20 that is 4% of the town a year.

**How far apart**
Direction right, absorption 10-50× too generous — defensible for a game where a park must feel like it does something, but it is why "parks fix everything" was a winning recipe. The exodus term is a *level* effect where the evidence is about *changes*; 4% a year leaving a mildly dirty town is Detroit-scale flight at SimCity-scale smog.

**The closest simple fix**
`pollution_exodus × max(0, pollution − 20)` so only pollution above the starting baseline pushes people out (Chen et al. measure changes). If parks should be honest: `park_absorb_first` 0.12 → 0.03; if not, say so in WORLD-RULES.

---

## 5. Mood (our "wellbeing")

**What researchers found**
- Unemployment hurts far beyond lost pay. Being unemployed costs about 1.3 points on a 0-10 life-satisfaction scale in Germany, 0.5-2.5 across Europe, and the gap "remains very large even after controlling for income"; people do not get used to it ([Clark & Oswald 1994](https://academic.oup.com/ej/article-abstract/104/424/648/5158769); [Winkelmann & Winkelmann 1998](https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0335.00111); [IZA World of Labor](https://wol.iza.org/articles/unemployment-and-happiness/long)). Each point of regional unemployment also costs the *employed* 0.04 points ([same source](https://wol.iza.org/articles/unemployment-and-happiness/long)). Losing a job leaves a permanent scar even after re-employment ([Lucas et al. 2004](https://journals.sagepub.com/doi/abs/10.1111/j.0963-7214.2004.01501002.x)).
- People adapt to income: 65% of a pay rise's happiness effect is gone within four years ([Di Tella, Haisken-DeNew & MacCulloch 2010](https://www.nber.org/papers/w13159)).
- Air pollution lowers life satisfaction across ten European countries ([Welsch 2006](https://ideas.repec.org/a/eee/ecolec/v58y2006i4p801-813.html)); with a clean natural experiment the effect is larger than naive estimates ([Luechinger 2009](https://academic.oup.com/ej/article-abstract/119/536/482/5089560)).
- The tax *rate* itself is not what makes people unhappy. Across 54 nations, "the overall tax rate and government spending were not associated with the subjective well-being of nations"; progressivity was, through satisfaction with public goods ([Oishi, Schimmack & Diener 2012](https://journals.sagepub.com/doi/abs/10.1177/0956797611420882)).
- Household debt is linked to stress and depression ([Sweet et al. 2013](https://www.sciencedirect.com/science/article/abs/pii/S0277953613002839)). Evidence on *public* debt is mixed: in well-governed countries more government debt goes with *higher* wellbeing ([Economics of Governance 2024](https://link.springer.com/article/10.1007/s10101-024-00309-9)).

**What our world does**
Target = 45 + 30 × employment + housing (±3) − 0.35 × pollution − 60 × tax + 0.25 × services − 10 × interest per head − 3 per 1000 of deficit; happiness moves halfway to target each year `[happiness_inertia = 0.5]`. Default target: 73. Debt at the 3000 cap costs 2.4 points.

**How far apart**
The unemployment weight is about right: 10 points of unemployment costs us 3 mood points; the literature implies roughly 1.7 (1.3 for the jobless plus 0.4 spillover, on a 0-100 scale). The hole is that unemployment is never above zero (see Jobs). The tax term is the one with the wrong sign in the literature: we charge 9 points at 15% regardless of what the money buys. Debt "barely hurts" because the cap is low, but the literature does not support a big public-debt penalty either; the real channel is services collapsing, which we already have. Inertia at 0.5 is a fair one-year half-life; note we model inertia, not adaptation: our citizens never get used to anything, which is right for unemployment and wrong for income.

**The closest simple fix**
Scale the tax penalty by what it buys: `tax_unhappiness × tax × (1 − services/100)` (Oishi: it is public goods, not the rate). Already on the PLAN TODO. Leave the debt weight; fix Jobs and mood will move on its own.

---

## 6. Resilience

**What researchers found**
- Regional economists split resilience into *resistance* (how far employment falls in a shock, usually relative to the national fall), *recovery* (how fast and how fully it comes back), and *re-orientation* ([Martin & Sunley 2015](https://academic.oup.com/joeg/article-abstract/15/1/1/960842)). There is "neither a universally accepted definition nor an agreed methodology" ([Regional Studies, Regional Science 2022](https://www.tandfonline.com/doi/full/10.1080/21681376.2022.2092418)).
- Every measure needs a shock. Resilience is observed *after* a recession; a region that never had one has no resilience score.

**What our world does**
No exogenous shocks: seeds change the starting city, not the weather. A dip is any year 15% below the running peak of jobs, treasury or happiness; a recovery is a return to 95%. Score 7 + 1.5 × recoveries − 1.5 × unrecovered dips; a term ending early scores ≤ 2.

**How far apart**
Recovery-to-95% is a fair "recoverability" measure. Missing: any shock to recover from (all our dips are self-inflicted, so resilience mostly re-scores prudence) and any measure of *speed*.

**The closest simple fix**
One seeded shock per term: in a year drawn from 5-15, jobs fall 10% (a mild Okun recession); score `7 − 0.5 × years spent in a dip + 1.5 × recoveries`. About six lines, and it gives the Reformer something to learn from.

---

## 6b. Toy economies in AI research, and what their rules were

- **The AI Economist** (Salesforce): a 2-D grid where agents gather wood and stone, trade, and build houses; a "planner" agent sets income-tax brackets at the start of each of 10 tax years of 100 steps. Agent skill follows a Pareto (heavy-tailed) distribution, so a few agents earn most. The planner's objective is equality × productivity ([Zheng et al., *Science Advances* 2022](https://www.science.org/doi/10.1126/sciadv.abk2607)). It has income, tax and inequality; it has no pollution, housing stock, or mood. Its lesson for us: taxable income must come from something agents *did*, or the planner learns nothing.
- **gym-city** wraps Micropolis (open-source SimCity 1) for reinforcement learning; reward is usually population. Agents converge on tiling residential zones around one power plant, a local optimum ([gym-city](https://github.com/smearle/gym-city)). This is the same pathology as our parks-plus-factories recipe: a single lever that the scorer cannot see through.
- Other urban RL benchmarks are narrower than ours: CityLearn (building energy), CityFlow (traffic), and DRL land-use layout. None grades a mayor on six criteria, which is why our scoreboard has to be built from the economics rather than borrowed.

---

## 7. Levers and their side effects

| Lever | What the literature says it does | What ours does |
|---|---|---|
| Set tax | Revenue on income/property; business elasticity −0.1 to −0.5 (Bartik); rate itself not tied to wellbeing, services are (Oishi) | Revenue on all jobs; cliff at 30%; −60 × rate on mood regardless of services |
| Build housing | Attracts people if jobs exist; imports unemployment if not (Forrester); above ~8% vacancy rents fall | Same trap; no price; ±3 mood; wide "good" band |
| Build factory | Jobs need workers or they go unfilled (Beveridge); primary polluter (SimCity) | 150 jobs land in 2 years and are always "filled"; +2 smoke |
| Build park | <1% concentration change (Nowak); raises residential demand (TheoTown, Skylines) | 12% absorption, diminishing; no direct mood or demand effect |
| Fund transit | Cuts emissions per trip; raises land value/accessibility (Lowry, SimCity) | −1 pollution per level; upkeep 40 |
| Fund services | Main channel from taxes to satisfaction (Oishi); Detroit shows the collapse | +12 points now, −4 decay, +0.25 mood per point. Matches |
| Subsidize business | "But-for" effects are small; most subsidised jobs would have come anyway (Bartik) | +40 permanent jobs each. Generous but same sign |
| Borrow | Ceilings of 5-7% of property value; breach means service collapse and flight (Detroit, Stockton) | Ceiling ≈ 5 years' revenue; austerity when broke. Matches, but the ceiling is reached with only 2.4 mood points of pain |

---

## 8. Where our world is already scientific

- **It is a system-dynamics model.** Stocks, one-year steps, delays, deterministic given a seed: exactly Forrester's method, and the pending queue is his construction lag.
- **The housing trap is Forrester's own headline result,** reproduced from first principles.
- **Workforce 60%** vs the real 62%.
- **The debt ceiling is the right order of magnitude** (a few years of revenue ≈ 5-7% of property value) and **austerity when broke is Detroit's story:** cannot pay staff, services decay, people leave.
- **Happiness inertia** with a one-year half-life is a reasonable reading of the panel evidence; **the unemployment weight** is within 2× of the measured effect.
- **Diminishing park absorption** has the right shape, only the wrong scale.
- **Pollution and tax flight point the right way.**
- **Consultants with fixed, opposite biases** are a design choice from the memory experiment, not from economics; the literature offers no calibration for them, and none is needed.

What is *not* defensible even for a game: an economy where a job needs no worker, because it removes the one variable (unemployment) that the wellbeing literature says matters most.

---

## 9. Summary table

| Criterion | Biggest gap | Fix | Source | Lines |
|---|---|---|---|---|
| Jobs | 900 jobs for 600 workers, always "filled" | `filled = min(jobs, workforce)`; excess jobs shrink 10%/yr; start at 540 jobs | Beveridge curve; Skylines demand rule | 3 |
| Homes | Passive mayor scores 10; no price, no decay | Band 1.03-1.10, drop +2; housing −1%/yr | Rosen & Smith 1983; Glaeser & Gyourko 2005 | 3 |
| Money | Tax on phantom jobs; cliff at 30% | Tax `min(jobs, workforce)`; drift toward `jobs × (0.15/tax)^0.3` | Bartik 1992; CRS Laffer report | 2 |
| Air | Parks 10-50× too strong; 4%/yr flight at baseline | Exodus on pollution above 20; optionally absorb 0.03 | Nowak 2014; Chen, Oliva & Zhang 2017 | 2 |
| Mood | Tax hurts regardless of services; unemployment never > 0 | Tax penalty × (1 − services/100) | Oishi, Schimmack & Diener 2012 | 1 |
| Resilience | Nothing to recover from; no speed | One seeded −10% jobs shock; score years in dip | Martin & Sunley 2015 | ~6 |

---

## Sources

- Forrester, *Urban Dynamics* (1969), housing result summarised in Jarzynski, System Dynamics Society 2006: https://proceedings.systemdynamics.org/2006/proceed/papers/JARZY255.pdf
- Attractiveness principle: https://en.wikipedia.org/wiki/Attractiveness_principle
- SimCity and Forrester, *Logic Magazine*: https://logicmag.io/play/model-metropolis/
- Micropolis (SimCity 1) manual, "Inside the simulator": https://github.com/danielellis/micropolis/blob/master/micropolis-activity/manual/inside.html
- Cities: Skylines wiki, Zoning: https://skylines.paradoxwikis.com/Zoning
- TheoTown wiki, underlying mechanics: https://theotown.fandom.com/wiki/The_Underlying_Mechanics
- BLS, CPS concepts and definitions: https://www.bls.gov/cps/definitions.htm
- FRED, labor force participation rate: https://fred.stlouisfed.org/series/CIVPART
- Beveridge curve: https://en.wikipedia.org/wiki/Beveridge_curve
- Okun's law: https://en.wikipedia.org/wiki/Okun%27s_law
- Tax Policy Center, sources of state and local revenue: https://taxpolicycenter.org/briefing-book/what-are-sources-revenue-state-and-local-governments
- Bartik (1992), effects of state and local taxes on economic development: https://doi.org/10.1177/089124249200600110
- Congressional Research Service, revenue-maximizing corporate tax rate: https://www.congress.gov/crs-product/R48913
- NABL, municipal debt limits: https://www.nabl.org/bond-basics/debt-limit/
- CNN Money, Detroit 2013: https://money.cnn.com/2013/07/19/news/economy/detroit-streetlights-police
- Washington Post, Detroit census 2010: http://www.washingtonpost.com/wp-dyn/content/article/2011/03/22/AR2011032202683.html
- Bridge Michigan, Stockton and Vallejo: https://bridgemi.com/michigan-government/stockton-vallejo-warn-detroit-you-aint-seen-nothin-yet/
- Rosen & Smith (1983), natural vacancy rate: https://econpapers.repec.org/article/aeaaecrev/v_3a73_3ay_3a1983_3ai_3a4_3ap_3a779-86.htm
- Texas Real Estate Research Center on natural vacancy: https://trerc.tamu.edu/article/rent-natural-vacancy-rates/
- Glaeser & Gyourko (2005), Urban Decline and Durable Housing: https://www.nber.org/papers/w8598
- Lowry (1964), A Model of Metropolis: https://www.rand.org/pubs/research_memoranda/RM4035.html
- Tiebout (1956): https://escholarship.org/uc/item/9fq454wm
- Roback (1982), Wages, Rents, and the Quality of Life: https://www.journals.uchicago.edu/doi/abs/10.1086/261120
- Nowak et al. (2014), tree effects on air quality: https://www.fs.usda.gov/nrs/pubs/jrnl/2014/nrs_2014_nowak_001.pdf
- Chen, Oliva & Zhang (2017), air pollution and migration: https://www.nber.org/papers/w24036
- Clark & Oswald (1994), Unhappiness and Unemployment: https://academic.oup.com/ej/article-abstract/104/424/648/5158769
- Winkelmann & Winkelmann (1998): https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0335.00111
- IZA World of Labor, Unemployment and happiness: https://wol.iza.org/articles/unemployment-and-happiness/long
- Lucas, Clark, Georgellis & Diener (2004), set point: https://journals.sagepub.com/doi/abs/10.1111/j.0963-7214.2004.01501002.x
- Di Tella, Haisken-DeNew & MacCulloch (2010), adaptation: https://www.nber.org/papers/w13159
- Welsch (2006), air pollution and happiness: https://ideas.repec.org/a/eee/ecolec/v58y2006i4p801-813.html
- Luechinger (2009), valuing air quality: https://academic.oup.com/ej/article-abstract/119/536/482/5089560
- Oishi, Schimmack & Diener (2012), progressive taxation and wellbeing: https://journals.sagepub.com/doi/abs/10.1177/0956797611420882
- Sweet et al. (2013), household debt and health: https://www.sciencedirect.com/science/article/abs/pii/S0277953613002839
- Government debt and wellbeing, 125 countries (2024): https://link.springer.com/article/10.1007/s10101-024-00309-9
- Martin & Sunley (2015), regional economic resilience: https://academic.oup.com/joeg/article-abstract/15/1/1/960842
- Regional economic resilience, system approach (2022): https://www.tandfonline.com/doi/full/10.1080/21681376.2022.2092418
- Zheng et al., The AI Economist, *Science Advances* (2022): https://www.science.org/doi/10.1126/sciadv.abk2607
- gym-city, Micropolis as an RL environment: https://github.com/smearle/gym-city
