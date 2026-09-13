"""Deterministic city world.

Same city, same seed, same actions -> byte-identical trajectory, on any machine.

Vocabulary: a *step* is one year. An *episode* is one term of office (20 years).

Design rules (see PLAN.md 1.1 and docs/WORLD-RULES.md for every number and why):
- State is seven numbers with a plain meaning. Everything else is derived.
- Two kinds of actions: world levers (identical for every mayor) and loop
  actions (information-gathering; results computed here, deterministically).
- `step()` is a pure function of (params, state, actions, seed, year). No globals, no I/O.
- Every change to a number is an Event with a cause and the year it was decided.
- Slow effects sit in a pending queue, so a decision's consequence can land later.
- A do-nothing year is valid. Nothing goes NaN or infinite.
- One lever looks great and is secretly ruinous: housing spam.
- No number lives in this file. They all live in sim/params.py.

No third-party dependencies on purpose: the sim must run with a bare python3.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any

from sim.params import DEFAULT, Params, params_for

HORIZON_YEARS = DEFAULT.horizon  # kept for callers/tests

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    year: int = 0
    population: float = 1000.0
    housing: float = 1100.0
    jobs: float = 900.0
    treasury: float = 500.0
    pollution: float = 20.0
    happiness: float = 60.0
    services: float = 50.0
    # bookkeeping a citizen would not name, but the world needs
    tax_rate: float = 0.15
    transit: int = 1
    factories: int = 3
    parks: int = 2
    debt: float = 0.0
    lots_extra: int = 0  # land bought beyond lots_total
    unhappy_years: int = 0
    broke_years: int = 0

    @classmethod
    def from_params(cls, p: Params) -> "State":
        return cls(
            population=p.start_population, housing=p.start_housing, jobs=p.start_jobs,
            treasury=p.start_treasury, pollution=p.start_pollution, happiness=p.start_happiness,
            services=p.start_services, tax_rate=p.start_tax_rate, transit=p.start_transit,
            factories=p.start_factories, parks=p.start_parks, debt=p.start_debt,
        )

    # ----- derived, never stored ------------------------------------------
    def employment_rate(self, p: Params = DEFAULT) -> float:
        workforce = max(self.population * p.workforce_share, 1.0)
        return min(1.0, self.jobs / workforce)

    def unemployment(self, p: Params = DEFAULT) -> float:
        return round(1.0 - self.employment_rate(p), 4)

    @property
    def housing_ratio(self) -> float:
        return self.housing / max(self.population, 1.0)

    def lots_used(self, p: Params = DEFAULT) -> int:
        return (self.factories * p.lots_per_factory + self.parks * p.lots_per_park
                + int(self.housing // 100) * p.lots_per_100_housing)

    def lots_free(self, p: Params = DEFAULT) -> int:
        return p.lots_total + self.lots_extra - self.lots_used(p)

    def economy_tier(self, p: Params = DEFAULT) -> int:
        """0..3, drives the renderer (horses vs cars, shuttered vs open)."""
        score = (self.employment_rate(p) * 40 + min(max(self.treasury, 0) / 2000, 1.0) * 20
                 + self.happiness * 0.4)
        return 0 if score < 35 else 1 if score < 55 else 2 if score < 75 else 3

    def public(self, p: Params = DEFAULT) -> dict[str, Any]:
        """What a mayor (or a citizen) is allowed to see."""
        d = {
            "year": self.year,
            "population": round(self.population),
            "housing": round(self.housing),
            "jobs": round(self.jobs),
            "treasury": round(self.treasury),
            "pollution": round(self.pollution, 1),
            "happiness": round(self.happiness, 1),
            "services": round(self.services, 1),
            "tax_rate": self.tax_rate,
            "transit_level": self.transit,
            "factories": self.factories,
            "parks": self.parks,
            "debt": round(self.debt),
            "unemployment": self.unemployment(p),
            "housing_ratio": round(self.housing_ratio, 2),
            "economy_tier": self.economy_tier(p),
        }
        if p.land_enabled:
            d["lots_free"] = self.lots_free(p)
            d["lots_total"] = p.lots_total + self.lots_extra
        return d


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def world_levers(p: Params = DEFAULT) -> dict[str, dict[str, Any]]:
    levers = {
        "set_tax": {"cost": 0, "delay": 0, "arg": "rate", "range": p.tax_range},
        "build_housing": {"cost": p.housing_cost, "delay": p.housing_delay, "arg": "units", "range": p.housing_range},
        "build_factory": {"cost": p.factory_cost, "delay": p.factory_delay, "arg": "count", "range": p.factory_range},
        "build_park": {"cost": p.park_cost, "delay": p.park_delay, "arg": "count", "range": p.park_range},
        "fund_transit": {"cost": p.transit_cost, "delay": p.transit_delay, "arg": "level", "range": p.transit_range},
        "fund_services": {"cost": p.services_cost, "delay": p.services_delay, "arg": "level", "range": p.services_range},
        "subsidize_business": {"cost": p.subsidy_cost, "delay": p.subsidy_delay, "arg": "amount", "range": p.subsidy_range},
        "borrow": {"cost": 0, "delay": 0, "arg": "amount", "range": p.borrow_range},
    }
    if p.land_enabled:
        levers["demolish"] = {"cost": 0, "delay": 0, "arg": "what", "range": None}  # what: factory|park|housing
        levers["buy_land"] = {"cost": p.buy_land_cost, "delay": 0, "arg": "lots", "range": p.buy_land_range}
    return levers


def loop_actions(p: Params = DEFAULT) -> dict[str, dict[str, Any]]:
    return {
        "consult_industrialist": {"cost": p.consult_fee},
        "consult_economist": {"cost": p.consult_fee},
        "hold_referendum": {"cost": p.referendum_fee},
        "read_last_report": {"cost": p.report_fee},
    }


WORLD_LEVERS = world_levers()  # defaults, for docs/tests
LOOP_ACTIONS = loop_actions()
MAX_ACTIONS_PER_YEAR = DEFAULT.max_actions_per_year


@dataclass
class Action:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """One change to one number, with the decision that caused it."""

    year: int
    variable: str
    delta: float
    cause_action: str
    cause_year: int
    note: str = ""


@dataclass
class Pending:
    fire_year: int
    variable: str
    delta: float
    cause_action: str
    cause_year: int
    note: str = ""


@dataclass
class World:
    seed: int
    params: Params = DEFAULT
    scenario: str = "default"
    state: State = field(default_factory=State)
    pending: list[Pending] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    ended: str | None = None
    start_public: dict[str, Any] | None = None  # the city on day one of this term (carried or fresh)

    def _rng(self, year: int, salt: str = "") -> random.Random:
        h = hashlib.sha256(f"{self.seed}:{year}:{salt}".encode()).hexdigest()
        return random.Random(int(h[:16], 16))


# ---------------------------------------------------------------------------
# Loop actions: information the world computes deterministically.
# ---------------------------------------------------------------------------


def _quiet_year_forecast(world: World) -> dict[str, float]:
    """Simulate one year with no actions on a copy. The honest base forecast."""
    w = copy.deepcopy(world)
    w.history = list(world.history)  # shallow is fine; step appends
    rec = step(w, [])
    s = rec["state"]
    return {"jobs_next_year": s["jobs"], "pollution_next_year": s["pollution"],
            "treasury_next_year": s["treasury"], "happiness_next_year": s["happiness"]}


def _naive_forecast(state: State, p: Params) -> dict[str, float]:
    return {
        "jobs_next_year": state.jobs * (1.0 + 0.02 * state.factories / 3),
        "pollution_next_year": state.pollution + p.factory_smoke * state.factories - p.park_cleans * state.parks,
        "treasury_next_year": state.treasury + state.tax_rate * state.jobs * p.wage
        - p.services_upkeep * state.services / p.services_upkeep_ref - state.debt * p.interest_rate,
        "happiness_next_year": state.happiness,
    }


def _forecast(world: World, bias: str) -> dict[str, Any]:
    """Base forecast, then a fixed bias per consultant. Both speak for a bloc."""
    p = world.params
    base = _quiet_year_forecast(world) if p.forecast_mode == "simulate" else _naive_forecast(world.state, p)
    if bias == "industrialist":
        base["jobs_next_year"] *= p.industrialist_jobs_bias
        base["pollution_next_year"] *= p.industrialist_pollution_bias
        advice = "Build factories. Jobs are the only thing that matters; smoke is the smell of money."
    else:
        base["treasury_next_year"] *= p.economist_treasury_bias
        base.pop("happiness_next_year", None)
        advice = "Raise taxes and cut services. A balanced budget cures everything."
    return {"forecast": {k: round(v, 1) for k, v in base.items()}, "advice": advice}


def _referendum(world: World, proposal: str) -> dict[str, Any]:
    p, s = world.params, world.state
    rng = world._rng(s.year, f"referendum:{proposal}")
    approval = s.happiness + p.popularity.get(proposal, 0) + rng.uniform(-p.referendum_noise, p.referendum_noise)
    return {"proposal": proposal, "approval_pct": round(max(0.0, min(100.0, approval)), 1),
            "turnout_pct": round(40 + s.services * 0.4, 1)}


def run_loop_action(world: World, action: Action) -> dict[str, Any]:
    """Compute a loop action's result. Charges treasury. Does not change the city."""
    p = world.params
    name = action.name
    world.state.treasury -= loop_actions(p)[name]["cost"]
    if name == "consult_industrialist":
        return _forecast(world, "industrialist")
    if name == "consult_economist":
        return _forecast(world, "economist")
    if name == "hold_referendum":
        return _referendum(world, str(action.args.get("proposal", "set_tax")))
    if name == "read_last_report":
        last = world.history[-1] if world.history else None
        return {"last_year_events": last["events"] if last else []}
    raise KeyError(name)


# ---------------------------------------------------------------------------
# The step function
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _validate(action: Action, p: Params) -> tuple[bool, str]:
    if action.name in loop_actions(p):
        return True, ""
    spec = world_levers(p).get(action.name)
    if spec is None:
        return False, f"unknown action {action.name!r}"
    arg = spec["arg"]
    if arg not in action.args:
        return False, f"{action.name} needs {arg!r}"
    if spec["range"] is None:  # categorical arg (demolish)
        if action.args[arg] not in ("factory", "park", "housing"):
            return False, f"{action.name}.{arg} must be factory|park|housing"
        return True, ""
    lo, hi = spec["range"]
    try:
        v = float(action.args[arg])
    except (TypeError, ValueError):
        return False, f"{action.name}.{arg} is not a number"
    if v != v or v in (float("inf"), float("-inf")):
        return False, f"{action.name}.{arg} is not finite"
    action.args[arg] = _clamp(v, lo, hi)
    return True, ""


def step(world: World, actions: list[Action]) -> dict[str, Any]:
    """Advance one year. Returns the year's record (also appended to history)."""
    assert world.ended is None, "episode already ended"
    p, s = world.params, world.state
    year = s.year + 1
    events: list[Event] = []
    ignored: list[dict[str, Any]] = []
    loop_results: list[dict[str, Any]] = []
    levers = world_levers(p)
    loops = loop_actions(p)

    def emit(variable: str, delta: float, cause: str, cause_year: int, note: str = "") -> None:
        if abs(delta) < 1e-9:
            return
        events.append(Event(year, variable, round(delta, 3), cause, cause_year, note))

    def pay(cost: float, cause: str, note: str) -> None:
        s.treasury -= cost
        emit("treasury", -cost, cause, year, note)

    # ---- 1. accept up to max_actions_per_year valid actions --------------
    accepted: list[Action] = []
    for a in actions:
        ok, why = _validate(a, p)
        if not ok:
            ignored.append({"action": asdict(a), "why": why})
            continue
        if len(accepted) >= p.max_actions_per_year:
            ignored.append({"action": asdict(a), "why": f"over the {p.max_actions_per_year}-actions-per-year limit"})
            continue
        accepted.append(a)

    # ---- 2. loop actions first (they inform, they do not change the city) --
    for a in accepted:
        if a.name in loops:
            result = run_loop_action(world, a)
            loop_results.append({"action": a.name, "args": a.args, "result": result})
            emit("treasury", -loops[a.name]["cost"], a.name, year, "consultation fee")

    # ---- 3. world levers: pay now, queue the effect --------------------------
    for a in accepted:
        if a.name not in levers:
            continue
        spec = levers[a.name]
        arg = a.args[spec["arg"]]
        fire = year + spec["delay"]
        if a.name == "set_tax":
            emit("tax_rate", arg - s.tax_rate, a.name, year)
            s.tax_rate = arg
        elif a.name == "build_housing":
            lots_needed = int(arg // 100) * p.lots_per_100_housing
            if p.land_enabled and lots_needed > s.lots_free(p):
                ignored.append({"action": asdict(a), "why": f"needs {lots_needed} lots, {s.lots_free(p)} free"})
                continue
            pay(spec["cost"] * arg, a.name, "construction")
            world.pending.append(Pending(fire, "housing", arg, a.name, year, "housing completes"))
            if p.land_enabled:
                # reserve the lots now so two builds in one year can't both claim them;
                # the reservation is released when the housing lands and counts in lots_used
                s.lots_extra -= lots_needed
                world.pending.append(Pending(fire, "_lots_reserved", -lots_needed, a.name, year, ""))
        elif a.name == "build_factory":
            n = int(arg)
            if p.land_enabled and n * p.lots_per_factory > s.lots_free(p):
                ignored.append({"action": asdict(a), "why": f"needs {n * p.lots_per_factory} lots, {s.lots_free(p)} free"})
                continue
            pay(spec["cost"] * n, a.name, "construction")
            world.pending.append(Pending(fire, "factories", n, a.name, year, "factory opens"))
            if p.land_enabled:
                s.lots_extra -= n * p.lots_per_factory
                world.pending.append(Pending(fire, "_lots_reserved", -n * p.lots_per_factory, a.name, year, ""))
        elif a.name == "build_park":
            n = int(arg)
            if p.land_enabled and n * p.lots_per_park > s.lots_free(p):
                ignored.append({"action": asdict(a), "why": f"needs {n * p.lots_per_park} lots, {s.lots_free(p)} free"})
                continue
            pay(spec["cost"] * n, a.name, "construction")
            world.pending.append(Pending(fire, "parks", n, a.name, year, "park opens"))
            if p.land_enabled:
                s.lots_extra -= n * p.lots_per_park
                world.pending.append(Pending(fire, "_lots_reserved", -n * p.lots_per_park, a.name, year, ""))
        elif a.name == "fund_transit":
            level = int(arg)
            pay(spec["cost"] * level, a.name, "transit funding")
            world.pending.append(Pending(fire, "transit", level - s.transit, a.name, year, "transit line opens"))
        elif a.name == "fund_services":
            level = int(arg)
            pay(spec["cost"] * level, a.name, "services funding")
            gain = p.services_gain * level
            s.services = _clamp(s.services + gain, 0, 100)
            emit("services", gain, a.name, year)
        elif a.name == "subsidize_business":
            amt = int(arg)
            pay(spec["cost"] * amt, a.name, "subsidy")
            world.pending.append(Pending(fire, "jobs", p.subsidy_jobs * amt, a.name, year, "subsidized businesses hire"))
        elif a.name == "borrow":
            revenue_now = s.tax_rate * s.jobs * p.wage
            limit = max(p.credit_floor, p.credit_limit_years * revenue_now)
            if s.debt + arg > limit:
                ignored.append({"action": asdict(a), "why": f"lenders refuse: debt {round(s.debt)} + {round(arg)} would exceed the credit limit of {round(limit)} ({p.credit_limit_years:g} years of revenue)"})
                continue
            s.treasury += arg
            s.debt += arg
            emit("treasury", arg, a.name, year, "loan received")
            emit("debt", arg, a.name, year)
        elif a.name == "demolish":
            what = arg
            if what == "factory" and s.factories > 0:
                s.factories -= 1
                lost = p.factory_jobs
                s.jobs = max(0.0, s.jobs - lost)
                emit("factories", -1, a.name, year, "demolished")
                emit("jobs", -lost, a.name, year, "factory closed")
            elif what == "park" and s.parks > 0:
                s.parks -= 1
                emit("parks", -1, a.name, year, "demolished")
            elif what == "housing" and s.housing >= 100:
                s.housing -= 100
                emit("housing", -100, a.name, year, "demolished")
            else:
                ignored.append({"action": asdict(a), "why": f"nothing to demolish: {what}"})
        elif a.name == "buy_land":
            n = int(arg)
            pay(spec["cost"] * n, a.name, "land purchase")
            s.lots_extra += n
            emit("lots", n, a.name, year, "land bought")

    # ---- 4. fire pending consequences whose year has come --------------------
    still: list[Pending] = []
    for q in world.pending:
        if q.fire_year > year:
            still.append(q)
            continue
        if q.variable == "_lots_reserved":
            s.lots_extra -= q.delta  # release the reservation; the building now counts in lots_used
            continue
        if q.variable == "housing":
            s.housing += q.delta
        elif q.variable == "factories":
            s.factories += int(q.delta)
            jobs_gain = p.factory_jobs * q.delta
            s.jobs += jobs_gain
            emit("jobs", jobs_gain, q.cause_action, q.cause_year, "factory hiring")
        elif q.variable == "parks":
            s.parks += int(q.delta)
        elif q.variable == "transit":
            s.transit = int(_clamp(s.transit + q.delta, 0, 3))
        elif q.variable == "jobs":
            s.jobs += q.delta
        emit(q.variable, q.delta, q.cause_action, q.cause_year, q.note)
    world.pending = still

    # ---- 5. the economy turns -------------------------------------------------
    rng = world._rng(year, "economy")
    revenue = s.tax_rate * s.jobs * p.wage
    upkeep = (p.upkeep_per_head * s.population + p.transit_upkeep * s.transit
              + p.factory_upkeep * s.factories + p.services_upkeep * s.services / p.services_upkeep_ref)
    interest = s.debt * p.interest_rate
    s.treasury += revenue - upkeep - interest
    emit("treasury", revenue, "economy", year, "tax revenue")
    emit("treasury", -upkeep, "economy", year, "upkeep")
    if interest:
        emit("treasury", -interest, "borrow", year, "interest")

    # pollution: emissions minus cleaning
    emissions = p.factory_smoke * s.factories + p.population_smoke * s.population / 1000
    if p.park_mode == "absorb":
        share = 0.0
        for i in range(s.parks):
            share += p.park_absorb_first * (p.park_absorb_decay ** i)
        cleaning = s.pollution * min(share, 0.95) + p.transit_cleans * s.transit
        note = "emissions vs parks absorbing a share, transit"
    else:
        cleaning = p.park_cleans * s.parks + p.transit_cleans * s.transit
        note = "factories vs parks/transit"
    dp = emissions - cleaning + rng.uniform(-p.pollution_noise, p.pollution_noise)
    new_p = _clamp(s.pollution + dp, 0, 100)
    emit("pollution", new_p - s.pollution, "economy", year, note)
    s.pollution = new_p

    # services decay, plus austerity: a broke city cannot pay its teachers and nurses
    s.services = _clamp(s.services - p.services_decay, 0, 100)
    emit("services", -p.services_decay, "economy", year, "decay without funding")
    if s.treasury < 0:
        austerity = min(p.austerity_decay_cap, p.austerity_decay_per_1000 * (-s.treasury) / 1000)
        if austerity > 0:
            s.services = _clamp(s.services - austerity, 0, 100)
            emit("services", -austerity, "borrow" if s.debt > 0 else "economy", year, "austerity: the city cannot pay its staff")

    # jobs churn
    churn = 0.0
    cause = "economy"
    if s.tax_rate > p.tax_flight_threshold:
        churn -= p.tax_flight_rate * s.jobs
        cause = "set_tax"
    if s.services < p.services_flight_threshold:
        churn -= p.services_flight_rate * s.jobs
    if s.debt > max(p.credit_floor, p.credit_limit_years * revenue):
        churn -= p.debt_job_flight_rate * s.jobs
        cause = "borrow"
    if churn:
        s.jobs = max(0.0, s.jobs + churn)
        emit("jobs", churn, cause, year, "businesses close")

    # happiness
    lo, hi = p.housing_ratio_clamp
    target = (p.happiness_base
              + p.happiness_employment * s.employment_rate(p)
              + p.happiness_housing * _clamp(s.housing_ratio, lo, hi) - p.happiness_housing
              - p.happiness_pollution * s.pollution
              - p.tax_unhappiness * s.tax_rate
              + p.happiness_services * s.services
              - p.debt_unhappiness_per_head * (interest / max(s.population, 1.0))
              - p.deficit_unhappiness_per_1000 * max(0.0, -s.treasury) / 1000)
    target = _clamp(target, 0, 100)
    dh = (target - s.happiness) * p.happiness_inertia + rng.uniform(-p.happiness_noise, p.happiness_noise)
    new_h = _clamp(s.happiness + dh, 0, 100)
    emit("happiness", new_h - s.happiness, "economy", year, "employment, housing, pollution, tax, services")
    s.happiness = new_h

    # population
    room = s.housing - s.population
    inflow = p.move_in_rate * max(room, 0) * (0.5 + s.happiness / 200)
    outflow = s.population * (p.unemployment_exodus * s.unemployment(p) + p.pollution_exodus * s.pollution
                              + (p.misery_exodus if s.happiness < p.misery_threshold else 0))
    if room < 0:
        outflow += -room * p.overcrowding_exodus
    dpop = inflow - outflow
    s.population = max(0.0, s.population + dpop)
    emit("population", dpop, "economy", year, f"inflow {inflow:.0f}, outflow {outflow:.0f}")

    # ---- 6. end states ---------------------------------------------------------
    s.year = year
    s.unhappy_years = s.unhappy_years + 1 if s.happiness < p.revolt_floor else 0
    s.broke_years = s.broke_years + 1 if s.treasury < p.bankruptcy_floor else 0
    start_pop = world.history[0]["state_before"]["population"] if world.history else p.start_population
    if s.broke_years >= p.bankruptcy_years:
        world.ended = "bankruptcy"
    elif s.population < p.depopulation_share * start_pop:
        world.ended = "depopulation"
    elif s.unhappy_years >= p.revolt_years:
        world.ended = "revolt"
    elif year >= p.horizon:
        world.ended = "horizon"

    record = {
        "year": year,
        "state_before": world.history[-1]["state"] if world.history else (world.start_public or State.from_params(p).public(p)),
        "actions": [asdict(a) for a in accepted],
        "ignored": ignored,
        "loop_results": loop_results,
        "events": [asdict(e) for e in events],
        "pending_count": sum(1 for q in world.pending if not q.variable.startswith("_")),
        "state": s.public(p),
        "ended": world.ended,
        "scenario": world.scenario,
    }
    world.history.append(record)
    return record


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def new_world(seed: int, scenario: str | None = None, params: Params | None = None,
              carry: dict[str, Any] | None = None, term: int = 0) -> World:
    """A fresh city for the scenario, or, if `carry` is given, the city as the last term left it.

    Persistence (decided 2026-09-12): term two starts where term one ended. Debt, smoke,
    factories, land all carry. Year resets to 0; the unhappy/broke streak counters reset so
    a new term is not deposed on day one for the old term's misery. The seed is salted with
    the term index so noise differs between terms.
    """
    p = params_for(scenario, params or DEFAULT)
    if carry is None:
        st = State.from_params(p)
    else:
        st = State(
            population=carry["population"], housing=carry["housing"], jobs=carry["jobs"],
            treasury=carry["treasury"], pollution=carry["pollution"], happiness=carry["happiness"],
            services=carry["services"], tax_rate=carry["tax_rate"], transit=carry["transit_level"],
            factories=carry["factories"], parks=carry["parks"], debt=carry["debt"],
            lots_extra=carry.get("lots_total", p.lots_total) - p.lots_total if "lots_total" in carry else 0,
        )
    w = World(seed=seed * 1000 + term, params=p, scenario=scenario or "default", state=st)
    w.start_public = st.public(p)
    return w


def run_script(seed: int, script: list[list[Action]], scenario: str | None = None,
               params: Params | None = None) -> World:
    """Run a fixed action script (one list of actions per year). For tests and controls."""
    w = new_world(seed, scenario, params)
    i = 0
    while w.ended is None:
        actions = script[i] if i < len(script) else []
        step(w, [Action(a.name, dict(a.args)) for a in actions])
        i += 1
    return w


def trajectory_json(world: World) -> str:
    return json.dumps({"seed": world.seed, "ended": world.ended, "years": world.history}, sort_keys=True)


def trajectory_hash(world: World) -> str:
    return hashlib.sha256(trajectory_json(world).encode()).hexdigest()[:16]


if __name__ == "__main__":
    w = run_script(0, [])
    print(f"seed 0, do nothing: ended={w.ended} after {w.state.year} years, hash={trajectory_hash(w)}")
    print(json.dumps(w.state.public(), indent=1))
