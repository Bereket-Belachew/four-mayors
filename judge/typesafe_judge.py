"""Second LLM judge, on TypeSafe's machine-native evaluator (System One, model jev-latest).

TypeSafe is not a generator: it takes a text state and typed questions and returns calibrated
answers. The six rubric criteria become six `score` questions, each with a six-rung legend
(0..5, scaled to 0..10 so the three graders share one axis), and each answer carries a
confidence. Like the Claude judge: reported beside the deterministic scoreboard, never summed
into it, never enters any mayor's context.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests
import weave

from judge.judge import _compact

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = os.getenv("TYPESAFE_MODEL", "jev-latest")

# Each legend goes from worst (0) to best (5). The words paraphrase the hidden rubric.
QUESTIONS: dict[str, dict[str, Any]] = {
    "prosperity": {
        "type": "score",
        "instructions": "Prosperity over the whole term: jobs relative to population at the end, and the trend in jobs.",
        "criteria": [
            "Jobs collapsed; most working-age people have no work at the end",
            "Chronic high unemployment for most of the term",
            "Unemployment high but improving, or a late jobs collapse after a strong start",
            "Most people have work, jobs roughly flat",
            "Most people have work and jobs grew over the term",
            "Near-full employment sustained, jobs grew strongly with population",
        ],
    },
    "housing": {
        "type": "score",
        "instructions": "Housing adequacy: housing units per person should stay near 1.0-1.2 for most of the term. Overcrowding (below 0.9) and wasteful overbuilding (above 1.5) both count against.",
        "criteria": [
            "Severe overcrowding or massive overbuilding for most of the term",
            "Chronic shortage or glut most years",
            "In the healthy band less than half the years",
            "In the healthy band about half the years",
            "In the healthy band most years with brief excursions",
            "In the healthy band nearly every year",
        ],
    },
    "fiscal": {
        "type": "score",
        "instructions": "Fiscal health: treasury trend and debt. Ending deeply negative, or borrowing that produced no jobs or housing, scores low. Hoarding a large surplus while services decay also loses points.",
        "criteria": [
            "Bankrupt, or deeply negative treasury with heavy debt that bought nothing",
            "Large debt or falling treasury with little to show for it",
            "Treasury roughly flat but debt growing, or a surplus hoarded while services decayed",
            "Solvent, modest debt, treasury stable",
            "Treasury grew and debt was paid down or used productively",
            "Strong net worth growth, debt used only where it produced jobs or homes",
        ],
    },
    "environment": {
        "type": "score",
        "instructions": "Environment: the pollution trend across the term. Rising pollution scores low; reversing a rise scores high.",
        "criteria": [
            "Pollution rose sharply and never stopped rising",
            "Pollution rose for most of the term",
            "Pollution rose then plateaued",
            "Pollution roughly flat",
            "Pollution fell over the term",
            "A rise was reversed and pollution ended well below where it started",
        ],
    },
    "wellbeing": {
        "type": "score",
        "instructions": "Wellbeing: mean happiness across the term and its minimum. One deep dip costs more than a mild steady level.",
        "criteria": [
            "Happiness collapsed into revolt territory (below 25) for years",
            "Low mean happiness with at least one deep dip",
            "Middling happiness with a notable dip",
            "Middling happiness, no deep dip",
            "Good mean happiness, shallow dips only",
            "High and steady happiness the whole term",
        ],
    },
    "resilience": {
        "type": "score",
        "instructions": "Resilience: did the city recover from any dip in jobs, treasury or happiness? Was an early exit (bankruptcy, depopulation, revolt) avoided? A term that ended early scores at the bottom regardless of other numbers.",
        "criteria": [
            "Ended early by bankruptcy, depopulation or revolt",
            "Survived to year 20 but never recovered from a major dip",
            "Survived; partial recovery from dips",
            "Survived; recovered from most dips slowly",
            "Survived; recovered quickly from every dip",
            "Survived with no serious dip at all, buffers intact",
        ],
    },
}
CRITERIA = list(QUESTIONS)


@weave.op()
def judge_episode_typesafe(history: list[dict[str, Any]], ended: str, *, model: str = MODEL) -> dict[str, Any]:
    """Score one episode with TypeSafe System One. Returns 0-10 scores plus per-criterion confidence."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")
    traj = _compact(history) if history else "(EMPTY: no years were played)"
    state = (
        f"A city was governed for a term of up to 20 years. Term ended by: {ended}. Years played: {len(history)}.\n"
        "Each line is one year: the actions taken, then the resulting numbers.\n\n" + traj
    )
    r = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"state": state, "model": model, "questions": QUESTIONS},
        timeout=90,
    )
    r.raise_for_status()
    out = r.json()
    answers = out.get("answers", {})
    scores: dict[str, float] = {}
    confidence: dict[str, float] = {}
    for c in CRITERIA:
        a = answers.get(c, {})
        scores[c] = round(float(a.get("score", 0.0)) * 2.0, 2)  # legend 0..5 -> 0..10
        confidence[c] = round(float(a.get("confidence", 0.0)), 3)
    # the rubric's rule for a city that stopped existing: keep only the share of the term it survived.
    # TypeSafe answers six legends and has no notion of term length, so the rule is applied here, as arithmetic.
    survived = 1.0 if ended == "horizon" else min(1.0, len(history) / 20)
    if survived < 1.0:
        for c in CRITERIA:
            scores[c] = round(scores[c] * survived, 2)
    scores["total"] = round(sum(scores[c] for c in CRITERIA), 2)
    return {"model": out.get("model", model), "scores": scores, "confidence": confidence, "survived": survived, "usage": out.get("usage")}
