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
    w = new_world(2)
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
