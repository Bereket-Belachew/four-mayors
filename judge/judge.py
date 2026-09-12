"""LLM judge. Reads the hidden rubric and a trajectory; returns scores + verdict.

Runs on a different lab's model than the mayors (Claude), on purpose.
Its output is reported beside the deterministic scoreboard, never summed into it,
and never enters any mayor's context.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import weave

RUBRIC = (Path(__file__).parent / "rubric.md").read_text()
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-5")

CRITERIA = ["prosperity", "housing", "fiscal", "environment", "wellbeing", "resilience"]


def _compact(history: list[dict[str, Any]]) -> str:
    """Trajectory as one line per year: actions and the resulting state. Keeps the prompt small."""
    lines = []
    for y in history:
        acts = ", ".join(f"{a['name']}({json.dumps(a['args'])})" for a in y["actions"]) or "nothing"
        s = y["state"]
        lines.append(
            f"y{y['year']}: {acts} -> pop {s['population']} housing {s['housing']} jobs {s['jobs']} "
            f"treasury {s['treasury']} debt {s['debt']} pollution {s['pollution']} happiness {s['happiness']} "
            f"services {s['services']}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        return json.loads(m.group(0)) if m else {}


@weave.op()
def judge_episode(history: list[dict[str, Any]], ended: str, *, model: str = JUDGE_MODEL) -> dict[str, Any]:
    """Score one episode with the rubric. Empty history is scored too (anti-vacuity control)."""
    from anthropic import Anthropic

    client = Anthropic()
    traj = _compact(history) if history else "(EMPTY: no years were played)"
    prompt = (
        f"{RUBRIC}\n\nEPISODE ended by: {ended}. Years played: {len(history)}.\n\nTRAJECTORY:\n{traj}\n\n"
        'Respond with JSON only: {"scores": {"prosperity": n, "housing": n, "fiscal": n, "environment": n, '
        '"wellbeing": n, "resilience": n}, "verdict": "<one paragraph>", "key_decision": {"year": n, "action": "..."}}'
    )
    resp = client.messages.create(model=model, max_tokens=800, messages=[{"role": "user", "content": prompt}])
    text = "".join(getattr(b, "text", "") for b in resp.content)
    out = _extract_json(text)
    scores = {c: float(out.get("scores", {}).get(c, 0)) for c in CRITERIA}
    scores["total"] = round(sum(scores.values()), 2)
    return {"model": model, "scores": scores, "verdict": out.get("verdict", ""), "key_decision": out.get("key_decision")}
