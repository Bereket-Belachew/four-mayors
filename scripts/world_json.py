"""Regenerate web/data/world.json (the World tab's evidence) from the engine itself.

    .venv/bin/python scripts/world_json.py

Keeps the hand-written card texts (numbers / levers / info_actions / ends) but refreshes every number
in them that comes from sim/params.py, and re-runs the three example scripts plus the same-seed proof.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.params import DEFAULT as P  # noqa: E402
from sim.world import Action, run_script, trajectory_hash, world_levers  # noqa: E402
from judge.scoreboard import score_trajectory  # noqa: E402

OUT = Path("web/data/world.json")
KEYS = ["population", "jobs", "housing", "treasury", "pollution", "happiness", "services", "debt"]


def series(w):
    return {k: [y["state"][k] for y in w.history] for k in KEYS}


def example(label, w):
    return {"label": label, "ended": w.ended, "years": w.state.year,
            "score": score_trajectory(w.history, w.ended)["total"], "series": series(w)}


def blind_search(n=400, seed=0):
    """Random 20-year scripts; keep the best. Not a mayor, a control: what luck alone can reach."""
    rng = random.Random(1)
    levers = world_levers(P)
    names = [k for k in levers if k not in ("demolish", "buy_land")]
    best, best_w = -1, None
    for _ in range(n):
        script = []
        for _y in range(20):
            acts = []
            for _a in range(rng.choice([0, 1, 1, 2])):
                name = rng.choice(names); spec = levers[name]
                lo, hi = spec["range"]; val = rng.uniform(lo, hi)
                if spec["arg"] in ("count", "level", "amount") and name != "borrow":
                    val = int(round(val))
                if name == "borrow":
                    val = int(round(val / 100) * 100)
                if name == "set_tax":
                    val = round(val, 2)
                acts.append(Action(name, {spec["arg"]: val}))
            script.append(acts)
        w = run_script(seed, script)
        sc = score_trajectory(w.history, w.ended)["total"]
        if sc > best:
            best, best_w = sc, w
    return best_w


def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    nothing = run_script(0, [])
    spam = run_script(0, [[Action("build_housing", {"units": 400})] for _ in range(20)])
    best = blind_search()
    a, b = run_script(0, []), run_script(0, [])
    examples = {
        "nothing": example("Do nothing for 20 years", nothing),
        "spam": example("Build 400 homes every year (the trap)", spam),
        "best": example("The best script a blind search found", best),
        "same_seed_twice": {"label": "Same seed, same actions, twice", "identical": trajectory_hash(a) == trajectory_hash(b), "hash": trajectory_hash(a)[:12]},
    }
    # refresh the numbers that live in params
    numbers = old.get("numbers", [])
    starts = {"population": P.start_population, "housing": P.start_housing, "jobs": P.start_jobs, "treasury": P.start_treasury,
              "pollution": P.start_pollution, "happiness": P.start_happiness, "services": P.start_services}
    for n in numbers:
        if n["k"] in starts:
            n["start"] = starts[n["k"]]
        if n["k"] == "jobs":
            n["moves"] = (f"Only jobs someone holds pay tax; the workforce is {int(P.workforce_share*100)}% of the people. Up with factories, subsidies and low tax. "
                          f"Down with tax above {int(P.tax_reference*100)}%, services below {int(P.services_flight_threshold)}, debt over the credit limit, and once a term a recession takes {int(P.shock_jobs_drop*100)}%. "
                          f"Jobs above {P.labour_ceiling:g}× the workforce cannot find staff and leave.")
        if n["k"] == "housing":
            n["moves"] = f"Up when the mayor builds. Down {int(P.housing_depreciation*100)}% a year as old homes fall out of use. People fill half the empty homes each year."
        if n["k"] == "happiness":
            n["moves"] = (f"A target of {P.happiness_base:g} + {P.happiness_employment:g} × employment + homes ± 3 − {P.happiness_pollution:g} × pollution − {P.tax_unhappiness:g} × tax × (1 − services/100) "
                          f"+ {P.happiness_services:g} × services − debt interest per head − deficit; mood moves halfway there each year.")
    levers = old.get("levers", [])
    for l in levers:
        if l["k"] == "set_tax":
            l["law"] = (f"Revenue = rate × filled jobs × {P.wage:g}. Business drifts toward jobs × ({P.tax_reference:g}/rate)^{P.tax_elasticity:g}, "
                        f"{int(P.tax_drift*100)}% of the gap a year: at 30% it settles 19% below par, at 40% 26%. Tax hurts mood only as far as services fail to earn it.")
        if l["k"] == "build_housing":
            l["law"] = f"{P.housing_cost:g} per unit, lands next year. People move in at half the empty homes a year. Jobs do not follow. This is the trap. Homes also wear out {int(P.housing_depreciation*100)}% a year."
        if l["k"] == "build_factory":
            l["law"] = f"{P.factory_cost:g} each, {P.factory_jobs:g} jobs after {P.factory_delay} years, +{P.factory_smoke:g} smoke a year, {P.lots_per_factory} lots. Jobs beyond {P.labour_ceiling:g}× the workforce find no staff and leave."
        if l["k"] == "build_park":
            l["law"] = (f"{P.park_cost:g} each, lands next year. The first park absorbs {int(P.park_absorb_first*100)}% of ambient pollution, each next one {int(P.park_absorb_decay*100)}% of the previous. "
                        f"Deliberately 10-50× stronger than real trees (Nowak 2014: under 1%), so a park feels like it does something.")
    ends = [f"Bankruptcy: treasury below {P.bankruptcy_floor:g} for {P.bankruptcy_years} years",
            f"Depopulation: below {int(P.depopulation_share*100)}% of the start",
            f"Revolt: happiness below {P.revolt_floor:g} for {P.revolt_years} years",
            f"Otherwise year {P.horizon}"]
    out = {"examples": examples, "numbers": numbers, "levers": levers, "info_actions": old.get("info_actions", []), "ends": ends,
           "recession": {"years": list(P.shock_year_range), "drop": P.shock_jobs_drop, "text": f"Once a term, in a year drawn from the seed between {P.shock_year_range[0]} and {P.shock_year_range[1]}, a recession removes {int(P.shock_jobs_drop*100)}% of jobs. Every mayor gets one. Resilience is how fast the city climbs back."}}
    OUT.write_text(json.dumps(out, indent=1))
    for k in ("nothing", "spam", "best"):
        e = examples[k]; print(f"{k:8s} {e['ended']:10s} {e['years']:2d}y score {e['score']}")
    print("same seed twice identical:", examples["same_seed_twice"]["identical"])


if __name__ == "__main__":
    main()
