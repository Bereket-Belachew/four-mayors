"""The world's contract (PLAN.md 1.1.3, 1.1.5, 1.1.6)."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim.world import (  # noqa: E402
    HORIZON_YEARS,
    LOOP_ACTIONS,
    WORLD_LEVERS,
    Action,
    new_world,
    run_script,
    step,
    trajectory_hash,
    trajectory_json,
)


def _random_script(rng: random.Random, years: int = HORIZON_YEARS) -> list[list[Action]]:
    names = list(WORLD_LEVERS) + list(LOOP_ACTIONS)
    script = []
    for _ in range(years):
        year = []
        for _ in range(rng.randint(0, 4)):  # sometimes over the 3-action limit on purpose
            n = rng.choice(names)
            if n in WORLD_LEVERS and WORLD_LEVERS[n]["range"] is None:
                year.append(Action(n, {WORLD_LEVERS[n]["arg"]: rng.choice(["factory", "park", "housing", "bogus"])}))
            elif n in WORLD_LEVERS:
                spec = WORLD_LEVERS[n]
                lo, hi = spec["range"]
                v = rng.uniform(lo * 0.5, hi * 1.5)  # sometimes out of range on purpose
                year.append(Action(n, {spec["arg"]: v}))
            elif n == "hold_referendum":
                year.append(Action(n, {"proposal": rng.choice(list(WORLD_LEVERS))}))
            else:
                year.append(Action(n))
        script.append(year)
    return script


def test_same_seed_same_script_is_byte_identical():
    script = _random_script(random.Random(7))
    a = run_script(42, script)
    b = run_script(42, script)
    assert trajectory_json(a) == trajectory_json(b)
    assert trajectory_hash(a) == trajectory_hash(b)


def test_different_seed_differs():
    script = _random_script(random.Random(7))
    assert trajectory_hash(run_script(1, script)) != trajectory_hash(run_script(2, script))


def test_do_nothing_is_valid_and_reaches_an_end():
    w = run_script(0, [])
    assert w.ended in {"horizon", "bankruptcy", "depopulation", "revolt"}
    assert 1 <= w.state.year <= HORIZON_YEARS


def test_unknown_and_malformed_actions_are_ignored_not_fatal():
    w = new_world(3)
    rec = step(w, [Action("declare_war"), Action("build_housing"), Action("set_tax", {"rate": "lots"}),
                   Action("set_tax", {"rate": float("nan")})])
    assert len(rec["ignored"]) == 4
    assert rec["actions"] == []


def test_property_200_random_scripts_never_crash_and_stay_finite():
    for i in range(200):
        script = _random_script(random.Random(i))
        w = run_script(i, script)
        s = w.state
        for v in (s.population, s.housing, s.jobs, s.treasury, s.pollution, s.happiness, s.services):
            assert math.isfinite(v)
        assert 0 <= s.pollution <= 100 and 0 <= s.happiness <= 100 and 0 <= s.services <= 100
        assert s.population >= 0 and s.jobs >= 0 and s.housing >= 0
        assert w.ended is not None


def test_every_event_carries_a_cause():
    script = _random_script(random.Random(11))
    w = run_script(5, script)
    for year in w.history:
        for e in year["events"]:
            assert e["cause_action"] and e["cause_year"] >= 1
            assert e["variable"] in {"population", "housing", "jobs", "treasury", "pollution",
                                     "happiness", "services", "tax_rate", "transit", "factories",
                                     "parks", "debt", "lots"}


def test_delayed_consequence_lands_later_with_original_cause():
    w = new_world(9)
    step(w, [Action("build_factory", {"count": 1})])  # delay 2
    assert w.history[0]["pending_count"] == 1
    step(w, [])
    step(w, [])
    fired = [e for e in w.history[2]["events"] if e["variable"] == "factories"]
    assert fired and fired[0]["cause_action"] == "build_factory" and fired[0]["cause_year"] == 1


def test_housing_spam_is_a_trap():
    """Pure housing spam: population booms, jobs do not follow, and it ends badly within the horizon."""
    spam = [[Action("build_housing", {"units": 400})] for _ in range(HORIZON_YEARS)]
    w = run_script(0, spam)
    peak_pop = max(y["state"]["population"] for y in w.history)
    assert peak_pop > 1300, "population should boom first"
    assert w.ended != "horizon" or w.state.happiness < 40, "and then it should hurt"


def test_loop_actions_are_deterministic_and_do_not_change_the_city():
    w1, w2 = new_world(4), new_world(4)
    r1 = step(w1, [Action("consult_industrialist"), Action("hold_referendum", {"proposal": "set_tax"})])
    r2 = step(w2, [Action("consult_industrialist"), Action("hold_referendum", {"proposal": "set_tax"})])
    assert r1["loop_results"] == r2["loop_results"]
    plain = step(new_world(4), [])
    # same city numbers except the consultation fees
    for k in ("population", "housing", "jobs", "pollution", "happiness", "services"):
        assert r1["state"][k] == plain["state"][k]
    assert r1["state"]["treasury"] < plain["state"]["treasury"]


def test_land_is_finite_and_refuses_when_full():
    from sim.params import DEFAULT
    w = new_world(2, params=DEFAULT.with_(start_treasury=50_000.0))  # rich enough to hit the land limit before the money runs out
    p = w.params
    assert p.land_enabled
    free0 = w.state.lots_free(p)
    # order more factories than the land can hold, over several years
    for _ in range(30):
        if w.ended:
            break
        step(w, [Action("build_factory", {"count": 3}), Action("borrow", {"amount": 2000})])
    refused = [i for y in w.history for i in y["ignored"] if "lots" in i["why"]]
    assert refused, "land never bound"
    assert w.state.lots_free(p) >= 0
    assert w.state.lots_used(p) <= p.lots_total + w.state.lots_extra


def test_parks_cannot_zero_pollution_against_factories():
    w = run_script(0, [[Action("build_park", {"count": 3})] for _ in range(4)])
    assert w.state.parks >= 10
    assert w.state.pollution > 0


def test_citizens_live_the_debt():
    """Same borrowing script, with and without the debt rules: with them, lenders eventually refuse,
    austerity events appear, and the citizens are measurably less happy."""
    from sim.params import DEFAULT
    borrow = [[Action("borrow", {"amount": 2000}), Action("fund_services", {"level": 1})] for _ in range(20)]
    with_rules = run_script(0, borrow)
    without = run_script(0, borrow, params=DEFAULT.with_(austerity_decay_per_1000=0.0, debt_unhappiness_per_head=0.0,
                                                          deficit_unhappiness_per_1000=0.0, credit_floor=1e9, credit_limit_years=1e9))
    refused = [i for y in with_rules.history for i in y["ignored"] if "lenders refuse" in i["why"]]
    assert refused, "lenders never refused"
    austerity = [e for y in with_rules.history for e in y["events"] if "austerity" in e.get("note", "")]
    assert austerity, "no austerity event"
    mean = lambda w: sum(y["state"]["happiness"] for y in w.history) / len(w.history)
    assert mean(with_rules) < mean(without) - 3, (mean(with_rules), mean(without))


# ---- rules grounded in the literature (2026-09-13, docs/research/world-models.md) ----


def test_jobs_need_workers():
    """A vacancy pays no tax, and jobs no one can fill shrink away (Beveridge curve)."""
    from sim.params import DEFAULT
    p = DEFAULT
    rich = new_world(0, params=p.with_(start_jobs=2000.0))          # 2000 jobs for 600 workers
    par = new_world(0, params=p.with_(start_jobs=600.0))            # exactly the workforce
    r1 = step(rich, [])
    r2 = step(par, [])
    rev = lambda rec: next(e["delta"] for e in rec["events"] if e["variable"] == "treasury" and e["note"] == "tax revenue")
    assert abs(rev(r1) - rev(r2)) < 1e-6, "phantom jobs paid tax"
    assert rich.state.jobs < 2000.0, "unfilled jobs never shrank"
    assert any("no staff" in e["note"] for e in r1["events"] if e["variable"] == "jobs")


def test_recession_lands_once_per_term_and_is_seeded():
    a = run_script(3, [])
    b = run_script(3, [])
    shocks = [e for y in a.history for e in y["events"] if e["cause_action"] == "recession"]
    assert len(shocks) == 1 and 5 <= shocks[0]["year"] <= 15
    assert a.shock_year == b.shock_year
    assert new_world(3).shock_year != new_world(4).shock_year or new_world(3).shock_year != new_world(5).shock_year


def test_tax_is_a_slope_not_a_cliff():
    """Bartik: business drifts with the rate. 25% tax already loses jobs; 5% gains them; 15% is par."""
    from sim.params import DEFAULT
    p = DEFAULT.with_(shock_enabled=False, start_jobs=600.0)
    def jobs_after(rate):
        w = new_world(0, params=p)
        step(w, [Action("set_tax", {"rate": rate})])
        return w.state.jobs
    assert jobs_after(0.25) < jobs_after(0.15) < jobs_after(0.05)
    w = new_world(0, params=p); step(w, [])
    assert abs(w.state.jobs - 600.0) < 1e-6, "at the reference rate jobs should hold"


def test_do_nothing_decays_but_an_active_mayor_beats_it():
    """The starting city is not a free lunch and not a death trap."""
    from judge.scoreboard import score_trajectory
    nothing = run_script(0, [])
    assert nothing.ended == "horizon"
    active = run_script(0, [[Action("subsidize_business", {"amount": 2})]]
                        + [[Action("fund_services", {"level": 1})] if i % 3 == 0 else [] for i in range(19)])
    assert score_trajectory(active.history, active.ended)["total"] > score_trajectory(nothing.history, nothing.ended)["total"] + 5
