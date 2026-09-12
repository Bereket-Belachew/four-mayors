"""Deterministic scoreboard: the same six criteria as the rubric, computed by formula.

The LLM judge's score is reported beside this, never summed into it.
(Fana rule: a judged score never enters the reward path.)
"""
from __future__ import annotations

from typing import Any

CRITERIA = ["prosperity", "housing", "fiscal", "environment", "wellbeing", "resilience"]


def _clamp10(x: float) -> float:
    return round(max(0.0, min(10.0, x)), 2)


def score_trajectory(history: list[dict[str, Any]], ended: str) -> dict[str, float]:
    """history: the per-year records from sim.world.step. Empty history scores zero."""
    if not history:
        return {c: 0.0 for c in CRITERIA} | {"total": 0.0}
    states = [y["state"] for y in history]
    first = history[0]["state_before"]
    last = states[-1]

    # 1 prosperity: employment at end + jobs trend
    workforce = max(last["population"] * 0.6, 1)
    emp = min(1.0, last["jobs"] / workforce)
    jobs_trend = (last["jobs"] - first["jobs"]) / max(first["jobs"], 1)
    prosperity = _clamp10(emp * 8 + max(-2, min(2, jobs_trend * 4)))

    # 2 housing adequacy: share of years with ratio in [1.0, 1.2]
    ratios = [s["housing_ratio"] for s in states]
    good = sum(1 for r in ratios if 1.0 <= r <= 1.2) / len(ratios)
    bad = sum(1 for r in ratios if r < 0.9 or r > 1.5) / len(ratios)
    housing = _clamp10(10 * good - 5 * bad + 2)

    # 3 fiscal: NET WORTH (treasury minus debt) trend, ending position, hoarding while services decay
    nw_first = first["treasury"] - first.get("debt", 0)
    nw_last = last["treasury"] - last.get("debt", 0)
    tre_trend = (nw_last - nw_first) / 1000
    fiscal = 5 + max(-4, min(4, tre_trend))
    if nw_last < -1000:
        fiscal -= 3
    if last["debt"] > 0 and jobs_trend <= 0 and last["housing"] <= first["housing"]:
        fiscal -= 2  # borrowed for nothing
    if last["treasury"] > 3000 and last["services"] < 20:
        fiscal -= 2  # hoarding
    fiscal = _clamp10(fiscal)

    # 4 environment: pollution trend
    pol_trend = last["pollution"] - first["pollution"]
    environment = _clamp10(6 - pol_trend / 6)

    # 5 wellbeing: mean and min happiness
    hs = [s["happiness"] for s in states]
    wellbeing = _clamp10((sum(hs) / len(hs)) / 10 * 0.7 + min(hs) / 10 * 0.3)

    # 6 resilience: recovery from dips; early exit caps it
    if ended != "horizon":
        resilience = _clamp10(min(2.0, len(history) / 10))
    else:
        dips = 0
        recoveries = 0
        for key in ("jobs", "treasury", "happiness"):
            seq = [s[key] for s in states]
            peak = seq[0]
            in_dip = False
            for v in seq:
                if v < peak * 0.85 and not in_dip:
                    in_dip = True
                    dips += 1
                if in_dip and v >= peak * 0.95:
                    in_dip = False
                    recoveries += 1
                peak = max(peak, v)
        resilience = _clamp10(7 + (recoveries * 1.5) - (dips - recoveries) * 1.5)

    scores = {
        "prosperity": prosperity, "housing": housing, "fiscal": fiscal,
        "environment": environment, "wellbeing": wellbeing, "resilience": resilience,
    }
    scores["total"] = round(sum(scores.values()), 2)
    return scores
