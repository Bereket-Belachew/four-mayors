"""Deterministic scoreboard: the same six criteria as the rubric, computed by formula.

The LLM judge's score is reported beside this, never summed into it.
(Fana rule: a judged score never enters the reward path.)
"""
from __future__ import annotations

from typing import Any

CRITERIA = ["prosperity", "housing", "fiscal", "environment", "wellbeing", "resilience"]
HOUSING_BAND = (1.03, 1.10)   # the natural vacancy rate, 3-10% empty (Rosen & Smith 1983); was 1.0-1.2 with a free +2
HOUSING_BAD = (0.9, 1.5)
HORIZON = 20                 # a term that ends early keeps only the share of its marks it survived


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
    # full credit inside the natural-vacancy band, falling straight to zero at the bad edges
    def _credit(r: float) -> float:
        lo, hi = HOUSING_BAND
        blo, bhi = HOUSING_BAD
        if lo <= r <= hi:
            return 1.0
        if r < lo:
            return max(0.0, (r - blo) / (lo - blo))
        return max(0.0, (bhi - r) / (bhi - hi))
    ratios = [s["housing_ratio"] for s in states]
    good = sum(_credit(r) for r in ratios) / len(ratios)
    bad = sum(1 for r in ratios if r < HOUSING_BAD[0] or r > HOUSING_BAD[1]) / len(ratios)
    housing = _clamp10(10 * good - 5 * bad)

    # 3 fiscal: NET WORTH (treasury minus debt) trend, ending position, hoarding while services decay
    nw_first = first["treasury"] - first.get("debt", 0)
    nw_last = last["treasury"] - last.get("debt", 0)
    tre_trend = (nw_last - nw_first) / 1000
    fiscal = 5 + max(-4, min(4, tre_trend))
    if nw_last < -1000:
        fiscal -= 3
    if last["debt"] > 0 and jobs_trend <= 0 and last["housing"] <= first["housing"]:
        fiscal -= 2  # borrowed for nothing
    # hoarding: a large surplus while something the money could fix is getting worse
    declining = (last["pollution"] > first["pollution"] + 5) or (last["happiness"] < first["happiness"] - 3) \
        or (last["services"] < 30)
    if last["treasury"] > 3000 and declining:
        fiscal -= 2 + min(3, (last["treasury"] - 3000) / 5000)
    fiscal = _clamp10(fiscal)

    # 4 environment: pollution trend
    pol_trend = last["pollution"] - first["pollution"]
    environment = _clamp10(6 - pol_trend / 6)

    # 5 wellbeing: mean and min happiness
    hs = [s["happiness"] for s in states]
    wellbeing = _clamp10((sum(hs) / len(hs)) / 10 * 0.7 + min(hs) / 10 * 0.3)

    # 6 resilience: how fast the city climbs out of dips (Martin & Sunley: resistance + recovery);
    # every term now carries one seeded recession, so there is always something to recover from.
    if ended != "horizon":
        resilience = _clamp10(min(2.0, len(history) / 10))
    else:
        years_in_dip = 0
        recoveries = 0
        for key in ("jobs", "happiness"):  # treasury is a policy choice (investing dips it on purpose), not a shock
            seq = [s[key] for s in states]
            peak = seq[0]
            in_dip = False
            for v in seq:
                if v < peak * 0.85 and not in_dip:
                    in_dip = True
                if in_dip:
                    years_in_dip += 1
                if in_dip and v >= peak * 0.95:
                    in_dip = False
                    recoveries += 1
                peak = max(peak, v)
        resilience = _clamp10(7 - 0.5 * years_in_dip + 1.5 * recoveries)

    scores = {
        "prosperity": prosperity, "housing": housing, "fiscal": fiscal,
        "environment": environment, "wellbeing": wellbeing, "resilience": resilience,
    }
    if ended != "horizon":
        # bankruptcy, revolt or depopulation: the city as a going concern is gone. Every criterion keeps only
        # the share of the term it survived (a collapse in year 7 keeps 35% of its marks); resilience stays <= 2.
        survived = min(1.0, len(history) / HORIZON)
        for k in scores:
            scores[k] = round(scores[k] * survived, 2)
    scores["total"] = round(sum(scores.values()), 2)
    return scores
