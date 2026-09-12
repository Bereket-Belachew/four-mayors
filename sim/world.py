"""Deterministic city world.

Same city, same seed, same actions -> byte-identical trajectory, on any machine.

Vocabulary: a *step* is one year. An *episode* is one term of office (20 years).

Design rules (see PLAN.md 1.1):
- State is seven numbers with a plain meaning. Everything else is derived.
- Two kinds of actions: world levers (identical for every mayor) and loop
  actions (information-gathering; results computed here, deterministically).
- `step()` is a pure function of (state, actions, seed, year). No globals, no I/O.
- Every change to a number is an Event with a cause and the year it was decided.
- Slow effects sit in a pending queue, so a decision's consequence can land later.
- A do-nothing year is valid. Nothing goes NaN or infinite. Treasury may go
  negative and interest compounds.
- One lever looks great and is secretly ruinous: housing spam.

No third-party dependencies on purpose: the sim must run with a bare python3.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any

HORIZON_YEARS = 20

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    year: int = 0
    population: float = 1000.0  # people
    housing: float = 1100.0  # units (each unit houses one person)
    jobs: float = 900.0  # count
    treasury: float = 500.0  # money; may go negative
    pollution: float = 20.0  # 0..100
    happiness: float = 60.0  # 0..100
    services: float = 50.0  # 0..100
    # bookkeeping that is not "state" a citizen would name, but the world needs
    tax_rate: float = 0.15  # 0..0.40
    transit: int = 1  # 0..3 funding level, decays without funding
    factories: int = 3
    parks: int = 2
    debt: float = 0.0  # principal borrowed; interest compounds yearly
    unhappy_years: int = 0
    broke_years: int = 0

    # ----- derived, never stored ------------------------------------------
    @property
    def employment_rate(self) -> float:
        workforce = max(self.population * 0.6, 1.0)
        return min(1.0, self.jobs / workforce)

    @property
    def unemployment(self) -> float:
        return round(1.0 - self.employment_rate, 4)

    @property
    def housing_ratio(self) -> float:
        return self.housing / max(self.population, 1.0)

    @property
    def economy_tier(self) -> int:
        """0..3, drives the renderer (horses vs cars, shuttered vs open)."""
        score = (
            self.employment_rate * 40
            + min(max(self.treasury, 0) / 2000, 1.0) * 20
            + self.happiness * 0.4
        )
        if score < 35:
            return 0
        if score < 55:
            return 1
        if score < 75:
            return 2
        return 3

    def public(self) -> dict[str, Any]:
        """What a mayor (or a citizen) is allowed to see."""
        return {
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
            "unemployment": self.unemployment,
            "housing_ratio": round(self.housing_ratio, 2),
            "economy_tier": self.economy_tier,
        }


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

WORLD_LEVERS: dict[str, dict[str, Any]] = {
    # name: {cost per unit, delay in years, arg name, arg range}
    "set_tax": {"cost": 0, "delay": 0, "arg": "rate", "range": (0.0, 0.40)},
    "build_housing": {"cost": 15, "delay": 1, "arg": "units", "range": (10, 400)},
    "build_factory": {"cost": 300, "delay": 2, "arg": "count", "range": (1, 3)},
    "build_park": {"cost": 120, "delay": 1, "arg": "count", "range": (1, 3)},
    "fund_transit": {"cost": 150, "delay": 2, "arg": "level", "range": (0, 3)},
    "fund_services": {"cost": 200, "delay": 0, "arg": "level", "range": (0, 3)},
    "subsidize_business": {"cost": 100, "delay": 1, "arg": "amount", "range": (1, 5)},
    "borrow": {"cost": 0, "delay": 0, "arg": "amount", "range": (100, 2000)},
}

LOOP_ACTIONS: dict[str, dict[str, Any]] = {
    "consult_industrialist": {"cost": 30},
    "consult_economist": {"cost": 30},
    "hold_referendum": {"cost": 60},
    "read_last_report": {"cost": 0},
}

MAX_ACTIONS_PER_YEAR = 3
INTEREST_RATE = 0.08
BANKRUPTCY_FLOOR = -3000.0
REVOLT_FLOOR = 25.0


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
    state: State = field(default_factory=State)
    pending: list[Pending] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)  # per-year records
    ended: str | None = None  # None while running; else exit reason

    # ----- rng ------------------------------------------------------------
    def _rng(self, year: int, salt: str = "") -> random.Random:
        h = hashlib.sha256(f"{self.seed}:{year}:{salt}".encode()).hexdigest()
        return random.Random(int(h[:16], 16))


# ---------------------------------------------------------------------------
# Loop actions: information the world computes deterministically. The LLM
# only puts words on these numbers.
# ---------------------------------------------------------------------------


def _forecast(state: State, bias: str) -> dict[str, Any]:
    """Naive one-year forecast, then a fixed bias per consultant.

    The industrialist underestimates pollution and overestimates jobs.
    The economist ignores happiness and overweights the treasury.
    Both speak for a bloc, so their reports read as many voices.
    """
    base = {
        "jobs_next_year": state.jobs * (1.0 + 0.02 * state.factories / 3),
        "pollution_next_year": state.pollution + 2.0 * state.factories - 1.5 * state.parks,
        "treasury_next_year": state.treasury
        + state.tax_rate * state.jobs * 3.0
        - 60 * state.services / 50
        - state.debt * INTEREST_RATE,
        "happiness_next_year": state.happiness,
    }
    if bias == "industrialist":
        base["jobs_next_year"] *= 1.25
        base["pollution_next_year"] *= 0.6
        advice = "Build factories. Jobs are the only thing that matters; smoke is the smell of money."
    else:
        base["treasury_next_year"] *= 1.15
        base.pop("happiness_next_year")
        advice = "Raise taxes and cut services. A balanced budget cures everything."
    return {"forecast": {k: round(v, 1) for k, v in base.items()}, "advice": advice}


def _referendum(world: World, proposal: str) -> dict[str, Any]:
    """Approval for a proposal, from the happiness distribution + the proposal's popularity."""
    s = world.state
    rng = world._rng(s.year, f"referendum:{proposal}")
    popularity = {
        "set_tax": -25, "build_housing": 10, "build_factory": 5, "build_park": 15,
        "fund_transit": 8, "fund_services": 12, "subsidize_business": -5, "borrow": 0,
    }.get(proposal, 0)
    approval = s.happiness + popularity + rng.uniform(-8, 8)
    approval = max(0.0, min(100.0, approval))
    return {"proposal": proposal, "approval_pct": round(approval, 1), "turnout_pct": round(40 + s.services * 0.4, 1)}


def run_loop_action(world: World, action: Action) -> dict[str, Any]:
    """Compute a loop action's result. Charges treasury. Does not change the city."""
    name = action.name
    spec = LOOP_ACTIONS[name]
    world.state.treasury -= spec["cost"]
    if name == "consult_industrialist":
        return _forecast(world.state, "industrialist")
    if name == "consult_economist":
        return _forecast(world.state, "economist")
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


def _validate(action: Action) -> tuple[bool, str]:
    if action.name in LOOP_ACTIONS:
        return True, ""
    spec = WORLD_LEVERS.get(action.name)
    if spec is None:
        return False, f"unknown action {action.name!r}"
    arg = spec["arg"]
    if arg not in action.args:
        return False, f"{action.name} needs {arg!r}"
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
    """Advance one year. Returns the year's record (also appended to history).

    Pure with respect to (world.seed, world.state, world.pending, actions):
    the same inputs produce the same outputs, byte for byte.
    """
    assert world.ended is None, "episode already ended"
    s = world.state
    year = s.year + 1
    events: list[Event] = []
    ignored: list[dict[str, Any]] = []
    loop_results: list[dict[str, Any]] = []

    def emit(variable: str, delta: float, cause: str, cause_year: int, note: str = "") -> None:
        if abs(delta) < 1e-9:
            return
        events.append(Event(year, variable, round(delta, 3), cause, cause_year, note))

    # ---- 1. accept up to MAX_ACTIONS_PER_YEAR valid actions ----------------
    accepted: list[Action] = []
    for a in actions:
        ok, why = _validate(a)
        if not ok:
            ignored.append({"action": asdict(a), "why": why})
            continue
        if len(accepted) >= MAX_ACTIONS_PER_YEAR:
            ignored.append({"action": asdict(a), "why": "over the 3-actions-per-year limit"})
            continue
        accepted.append(a)

    # ---- 2. loop actions first (they inform, they do not change the city) --
    for a in accepted:
        if a.name in LOOP_ACTIONS:
            result = run_loop_action(world, a)
            loop_results.append({"action": a.name, "args": a.args, "result": result})
            emit("treasury", -LOOP_ACTIONS[a.name]["cost"], a.name, year, "consultation fee")

    # ---- 3. world levers: pay now, queue the effect --------------------------
    for a in accepted:
        if a.name not in WORLD_LEVERS:
            continue
        spec = WORLD_LEVERS[a.name]
        arg = a.args[spec["arg"]]
        fire = year + spec["delay"]
        if a.name == "set_tax":
            emit("tax_rate", arg - s.tax_rate, a.name, year)
            s.tax_rate = arg
        elif a.name == "build_housing":
            cost = spec["cost"] * arg / 10
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "construction")
            world.pending.append(Pending(fire, "housing", arg, a.name, year, "housing completes"))
        elif a.name == "build_factory":
            n = int(arg)
            cost = spec["cost"] * n
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "construction")
            world.pending.append(Pending(fire, "factories", n, a.name, year, "factory opens"))
        elif a.name == "build_park":
            n = int(arg)
            cost = spec["cost"] * n
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "construction")
            world.pending.append(Pending(fire, "parks", n, a.name, year, "park opens"))
        elif a.name == "fund_transit":
            level = int(arg)
            cost = spec["cost"] * level
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "transit funding")
            world.pending.append(Pending(fire, "transit", level - s.transit, a.name, year, "transit line opens"))
        elif a.name == "fund_services":
            level = int(arg)
            cost = spec["cost"] * level
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "services funding")
            gain = 12.0 * level
            s.services = _clamp(s.services + gain, 0, 100)
            emit("services", gain, a.name, year)
        elif a.name == "subsidize_business":
            amt = int(arg)
            cost = spec["cost"] * amt
            s.treasury -= cost
            emit("treasury", -cost, a.name, year, "subsidy")
            world.pending.append(Pending(fire, "jobs", 40.0 * amt, a.name, year, "subsidized businesses hire"))
        elif a.name == "borrow":
            s.treasury += arg
            s.debt += arg
            emit("treasury", arg, a.name, year, "loan received")
            emit("debt", arg, a.name, year)

    # ---- 4. fire pending consequences whose year has come --------------------
    still: list[Pending] = []
    for p in world.pending:
        if p.fire_year > year:
            still.append(p)
            continue
        if p.variable == "housing":
            s.housing += p.delta
        elif p.variable == "factories":
            s.factories += int(p.delta)
            jobs_gain = 150.0 * p.delta
            s.jobs += jobs_gain
            emit("jobs", jobs_gain, p.cause_action, p.cause_year, "factory hiring")
        elif p.variable == "parks":
            s.parks += int(p.delta)
        elif p.variable == "transit":
            s.transit = int(_clamp(s.transit + p.delta, 0, 3))
        elif p.variable == "jobs":
            s.jobs += p.delta
        emit(p.variable, p.delta, p.cause_action, p.cause_year, p.note)
    world.pending = still

    # ---- 5. the economy turns -------------------------------------------------
    rng = world._rng(year, "economy")
    # revenue and running costs
    revenue = s.tax_rate * s.jobs * 3.0
    # a city costs money to run: per head, per transit line, per factory, plus funded services
    upkeep = 0.25 * s.population + 40.0 * s.transit + 20.0 * s.factories + 60.0 * s.services / 50
    interest = s.debt * INTEREST_RATE
    s.treasury += revenue - upkeep - interest
    emit("treasury", revenue, "economy", year, "tax revenue")
    emit("treasury", -upkeep, "economy", year, "upkeep")
    if interest:
        emit("treasury", -interest, "borrow", year, "interest")

    # pollution: factories add, parks and transit remove
    dp = 2.0 * s.factories - 1.5 * s.parks - 1.0 * s.transit + rng.uniform(-1, 1)
    new_p = _clamp(s.pollution + dp, 0, 100)
    emit("pollution", new_p - s.pollution, "economy", year, "factories vs parks/transit")
    s.pollution = new_p

    # services decay without funding
    decay = -4.0
    s.services = _clamp(s.services + decay, 0, 100)
    emit("services", decay, "economy", year, "decay without funding")

    # jobs churn: businesses close under high tax or low services
    churn = -0.02 * s.jobs * (1 if s.tax_rate > 0.30 else 0) - 0.01 * s.jobs * (1 if s.services < 20 else 0)
    if churn:
        s.jobs = max(0.0, s.jobs + churn)
        emit("jobs", churn, "set_tax" if s.tax_rate > 0.30 else "economy", year, "businesses close")

    # happiness: employment, housing, pollution, tax, services
    target = (
        45
        + 30 * s.employment_rate
        + 15 * _clamp(s.housing_ratio, 0.8, 1.2) - 15
        - 0.35 * s.pollution
        - 60 * s.tax_rate
        + 0.25 * s.services
    )
    target = _clamp(target, 0, 100)
    dh = (target - s.happiness) * 0.5 + rng.uniform(-2, 2)
    new_h = _clamp(s.happiness + dh, 0, 100)
    emit("happiness", new_h - s.happiness, "economy", year, "employment, housing, pollution, tax, services")
    s.happiness = new_h

    # population: people come for jobs and homes, leave for unemployment and smoke.
    # The housing-spam trap lives here: population follows housing fast, jobs do not.
    room = s.housing - s.population
    inflow = 0.5 * max(room, 0) * (0.5 + s.happiness / 200)
    outflow = s.population * (0.08 * s.unemployment + 0.002 * s.pollution + (0.03 if s.happiness < 35 else 0))
    if room < 0:
        outflow += -room * 0.5  # overcrowding
    dpop = inflow - outflow
    s.population = max(0.0, s.population + dpop)
    emit("population", dpop, "economy", year, f"inflow {inflow:.0f}, outflow {outflow:.0f}")

    # ---- 6. end states ---------------------------------------------------------
    s.year = year
    s.unhappy_years = s.unhappy_years + 1 if s.happiness < REVOLT_FLOOR else 0
    s.broke_years = s.broke_years + 1 if s.treasury < BANKRUPTCY_FLOOR else 0
    start_pop = world.history[0]["state_before"]["population"] if world.history else 1000
    if s.broke_years >= 2:
        world.ended = "bankruptcy"
    elif s.population < 0.2 * start_pop:
        world.ended = "depopulation"
    elif s.unhappy_years >= 3:
        world.ended = "revolt"
    elif year >= HORIZON_YEARS:
        world.ended = "horizon"

    record = {
        "year": year,
        "state_before": world.history[-1]["state"] if world.history else State().public() | {"population": start_pop},
        "actions": [asdict(a) for a in accepted],
        "ignored": ignored,
        "loop_results": loop_results,
        "events": [asdict(e) for e in events],
        "pending_count": len(world.pending),
        "state": s.public(),
        "ended": world.ended,
    }
    world.history.append(record)
    return record


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def new_world(seed: int) -> World:
    return World(seed=seed, state=State())


def run_script(seed: int, script: list[list[Action]]) -> World:
    """Run a fixed action script (one list of actions per year). For tests and controls."""
    w = new_world(seed)
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
