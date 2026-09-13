"""Every number the world runs on, in one place, with the name used in docs/WORLD-RULES.md.

Change a value here and the world changes. The logic in sim/world.py never hardcodes a number.
Flags (the *_enabled / *_mode entries) switch rules on and off so a change can be A/B'd.

Read docs/WORLD-RULES.md for the plain-language meaning of each entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class Params:
    # ---- horizon and slots -------------------------------------------------
    horizon: int = 20
    max_actions_per_year: int = 3

    # ---- starting city (the "default" scenario) -----------------------------
    start_population: float = 1000.0
    start_housing: float = 1100.0
    start_jobs: float = 540.0        # 900 -> 540 on 2026-09-13: 10% unemployment at the start (the Cities: Skylines player's target); 900 jobs for 600 workers was a labour shortage no model lets persist
    start_treasury: float = 500.0
    start_pollution: float = 20.0
    start_happiness: float = 60.0
    start_services: float = 50.0
    start_tax_rate: float = 0.15
    start_transit: int = 1
    start_factories: int = 3
    start_parks: int = 2
    start_debt: float = 0.0

    # ---- people -----------------------------------------------------------------
    workforce_share: float = 0.60      # share of population that can work (US labour-force participation is 62%)
    # ---- jobs need workers (2026-09-13, docs/research/world-models.md: Beveridge curve, SimCity/Skylines demand rule)
    tax_filled_jobs_only: bool = True  # tax is paid by people who work, never by a vacancy
    labour_ceiling: float = 1.10       # jobs above this multiple of the workforce cannot find staff...
    unfilled_shrink_rate: float = 0.10 # ...and shrink by this share of the excess each year ("no staff, business leaves")
    # ---- a recession once a term (Martin & Sunley: resilience needs a shock to recover from)
    shock_enabled: bool = True
    shock_year_range: tuple[int, int] = (5, 15)   # drawn from the seed, so the Reformer can learn it but not know it
    shock_jobs_drop: float = 0.10      # a mild Okun recession: 10% of jobs vanish that year

    # ---- money ------------------------------------------------------------------
    wage: float = 5.5                  # taxable money per FILLED job per year; revenue = tax * min(jobs, workforce) * wage. 3.0 -> 3.5 (2026-09-12) -> 5.5 (2026-09-13): once only filled jobs pay tax, full employment (600 workers at 15%) must cover the ~410 upkeep AND leave ~85/yr for one service level every three years; the 10%-unemployed start has ~35/yr of slack, so a mayor who never fixes unemployment can fund almost nothing
    upkeep_per_head: float = 0.25
    transit_upkeep: float = 40.0       # per level per year
    factory_upkeep: float = 20.0       # per factory per year
    services_upkeep: float = 60.0      # per year at services == services_upkeep_ref
    services_upkeep_ref: float = 50.0
    interest_rate: float = 0.08

    # ---- levers: cost, delay, arg range ---------------------------------------
    housing_cost: float = 1.5          # per unit
    housing_depreciation: float = 0.01 # share of homes falling out of use each year (Glaeser & Gyourko: housing is durable, decline is slow)
    housing_delay: int = 1
    housing_range: tuple[float, float] = (10, 400)
    factory_cost: float = 300.0
    factory_delay: int = 2
    factory_range: tuple[float, float] = (1, 3)
    factory_jobs: float = 150.0        # jobs per factory when it opens
    park_cost: float = 120.0
    park_delay: int = 1
    park_range: tuple[float, float] = (1, 3)
    transit_cost: float = 150.0        # per level
    transit_delay: int = 2
    transit_range: tuple[float, float] = (0, 3)
    services_cost: float = 150.0       # per level (200 -> 150, same reason)
    services_delay: int = 0
    services_range: tuple[float, float] = (0, 3)
    services_gain: float = 12.0        # points per level
    subsidy_cost: float = 100.0        # per unit
    subsidy_delay: int = 1
    subsidy_range: tuple[float, float] = (1, 5)
    subsidy_jobs: float = 40.0         # permanent jobs per unit
    borrow_range: tuple[float, float] = (100, 2000)
    tax_range: tuple[float, float] = (0.0, 0.40)

    # ---- information actions -------------------------------------------------
    consult_fee: float = 30.0
    referendum_fee: float = 60.0
    report_fee: float = 0.0
    industrialist_jobs_bias: float = 1.25
    industrialist_pollution_bias: float = 0.60
    economist_treasury_bias: float = 1.15
    referendum_noise: float = 8.0
    popularity: dict[str, float] = field(default_factory=lambda: {
        "set_tax": -25, "build_housing": 10, "build_factory": 5, "build_park": 15,
        "fund_transit": 8, "fund_services": 12, "subsidize_business": -5, "borrow": 0,
        "demolish": -10, "buy_land": -5,
    })
    forecast_mode: str = "simulate"    # "simulate" (step a quiet year on a copy) | "naive" (old formula)

    # ---- pollution ------------------------------------------------------------
    factory_smoke: float = 2.0         # per factory per year
    park_cleans: float = 1.5           # per park per year (fixed mode)
    transit_cleans: float = 1.0        # per level per year
    pollution_noise: float = 1.0
    pollution_baseline: float = 20.0   # people leave over pollution ABOVE this, not over the level (Chen, Oliva & Zhang 2017 measure changes)
    park_mode: str = "absorb"          # "fixed" (subtract park_cleans each) | "absorb" (share of ambient, diminishing)
    park_absorb_first: float = 0.12    # absorb mode: share of ambient pollution the first park removes per year
    park_absorb_decay: float = 0.80    # each additional park absorbs this fraction of the previous one's share
    population_smoke: float = 1.0      # per 1000 people per year (0 = old behavior)

    # ---- land ---------------------------------------------------------------------
    land_enabled: bool = True          # decided 2026-09-12 ~15:45 after a 52-park city
    lots_total: int = 81               # 12x12 grid minus roads
    lots_per_factory: int = 2
    lots_per_park: int = 1
    lots_per_100_housing: int = 1
    lots_per_civic: int = 1            # civic buildings appear per 12 services points (renderer only)
    buy_land_cost: float = 400.0       # per lot
    buy_land_range: tuple[float, float] = (1, 10)
    demolish_refund: float = 0.0

    # ---- debt is lived by the citizens (decided 2026-09-12 ~19:20) ---------
    austerity_decay_per_1000: float = 2.0   # extra services decay per year per 1000 of NEGATIVE treasury (the city cannot pay teachers)
    austerity_decay_cap: float = 8.0        # at most this much extra decay a year
    debt_unhappiness_per_head: float = 10.0 # happiness target penalty per unit of yearly interest per resident (26k debt / 1380 people ≈ 1.5 → −15)
    credit_limit_years: float = 5.0         # lenders refuse once debt exceeds this many years of tax revenue...
    credit_floor: float = 3000.0            # ...but every city can borrow at least this much in total
    deficit_unhappiness_per_1000: float = 3.0  # happiness target penalty per 1000 of negative treasury (unpaid wages, arrears)
    debt_job_flight_rate: float = 0.01      # jobs leaving per year while over the credit limit

    # ---- services -----------------------------------------------------------
    services_decay: float = 4.0

    # ---- jobs leaving --------------------------------------------------------
    tax_flight_mode: str = "slope"     # "slope" (Bartik 1992: a gentle curve from zero) | "cliff" (old: nothing below the threshold, 2%/yr above)
    tax_reference: float = 0.15        # the rate at which business is at par
    tax_elasticity: float = 0.30       # business settles at jobs × (reference/rate)^elasticity: 30% tax -> 19% below par, 40% -> 26%
    tax_drift: float = 0.10            # share of the gap closed each year
    tax_pull_cap: float = 1.30         # a tax cut can attract at most 30% more business
    tax_flight_threshold: float = 0.30 # cliff mode only
    tax_flight_rate: float = 0.02      # cliff mode only
    services_flight_threshold: float = 20.0
    services_flight_rate: float = 0.01

    # ---- happiness --------------------------------------------------------------
    happiness_base: float = 45.0
    happiness_employment: float = 30.0
    happiness_housing: float = 15.0
    housing_ratio_clamp: tuple[float, float] = (0.8, 1.2)
    happiness_pollution: float = 0.35
    tax_unhappiness: float = 60.0
    tax_unhappiness_services_scaled: bool = True  # Oishi, Schimmack & Diener 2012: the rate itself is not what hurts, it is what it fails to buy; penalty × (1 − services/100)
    happiness_services: float = 0.25
    happiness_inertia: float = 0.5
    happiness_noise: float = 2.0

    # ---- population -------------------------------------------------------------
    move_in_rate: float = 0.5
    unemployment_exodus: float = 0.08
    pollution_exodus: float = 0.002
    misery_threshold: float = 35.0
    misery_exodus: float = 0.03
    overcrowding_exodus: float = 0.5

    # ---- end states -------------------------------------------------------------
    bankruptcy_floor: float = -3000.0
    bankruptcy_years: int = 2
    bankruptcy_mood_shock: float = 25.0   # the day the city defaults: wages unpaid, pensions cut, credit gone. Happiness falls by this much (Detroit 2013), and the misery is inherited by the next term
    depopulation_share: float = 0.20
    revolt_floor: float = 25.0
    revolt_years: int = 3

    def with_(self, **changes: Any) -> "Params":
        return replace(self, **changes)


DEFAULT = Params()

# ---------------------------------------------------------------------------
# Hard starts. Each seed opens on a different problem, so a lesson learned on one
# city is tested on a different-looking one. Selected with `scenario_for(seed)`.
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "default": {},
    "unemployment": {  # 30% of the workforce idle
        "start_jobs": 420.0, "start_happiness": 48.0, "start_treasury": 400.0,
    },
    "smog": {  # a factory town choking
        "start_pollution": 70.0, "start_factories": 6, "start_parks": 0, "start_jobs": 660.0,  # 1300 -> 660 (2026-09-13): full employment plus a little excess, not 2 jobs per worker
        "start_happiness": 45.0,
    },
    "debt": {  # the last mayor borrowed
        "start_debt": 2500.0, "start_treasury": -800.0, "start_services": 30.0,
    },
    "housing_shortage": {  # homes for half the people
        "start_housing": 550.0, "start_population": 1000.0, "start_happiness": 42.0,
    },
}
SCENARIO_ORDER = ["unemployment", "smog", "debt", "housing_shortage"]


def scenario_for(seed: int) -> str:
    return SCENARIO_ORDER[seed % len(SCENARIO_ORDER)]


def params_for(scenario: str | None, base: Params = DEFAULT) -> Params:
    if not scenario or scenario == "default":
        return base
    return base.with_(**SCENARIOS[scenario])
