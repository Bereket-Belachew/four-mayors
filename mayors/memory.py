"""Memory policies: what a mayor reads before a term and writes after it.

This is the experiment. The inner loop (within a term) is identical for every
mayor; only these policies differ. See PLAN.md 1.2.2 and docs/WORLD-RULES.md §8.

  none             Caesar.      Nothing crosses a term boundary.
  opinion_log      Bureaucrat.  Raw loop-action outputs (forecasts, referenda), appended
                                forever. Opinions, never outcomes.
  lessons          Reformer.    Post-mortem -> at most 7 CONDITIONAL, PREDICTIVE lessons:
                                "when <condition>, <strategy>; expect <variable> <op> <value>
                                by year <n>". At the end of the next term each lesson is
                                reviewed against that term's year-by-year record: was it
                                applied, and did the prediction hold? Wrong -> confidence
                                down or deleted. Bounded, falsifiable.
  lessons_populist Populist.    Same mechanism, but the verdict is blended 2:1 with citizen
                                approval, except the two most confident lessons, which stay
                                outcome-only.

Redesigned 2026-09-12 ~15:30 after the first real run: the previous schema (lever ->
variable -> direction) produced lessons that restated the lever table and could never fail.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import weave

MAX_LESSONS = 7
LESSONS_PER_TERM = 4
OUTCOME_ANCHORED_SLOTS = 2
LESSON_REWARD = 0.25
LESSON_PENALTY = 0.30
LESSON_FLOOR = 0.20
APPROVAL_WEIGHT = 2.0

VARIABLES = {"population", "housing", "jobs", "treasury", "pollution", "happiness", "services", "debt"}


@dataclass
class Lesson:
    condition: str  # when the city looks like this...
    strategy: str  # ...do (or avoid) this...
    rule: str  # one-sentence form for the UI
    variable: str = ""  # ...and expect this number
    comparator: str = ""  # ">=" | "<="
    value: float | None = None  # to be on this side of this value
    by_year: int | None = None  # by this year of the term
    confidence: float = 0.5
    seen: int = 1
    history: list[str] = field(default_factory=list)

    def prediction_text(self) -> str:
        if self.variable and self.comparator and self.value is not None and self.by_year:
            return f"{self.variable} {self.comparator} {self.value:g} by year {self.by_year}"
        return "(no measurable prediction)"

    def testable(self) -> bool:
        return bool(self.variable in VARIABLES and self.comparator in (">=", "<=") and self.value is not None and self.by_year)


@dataclass
class Memory:
    policy: str
    lessons: list[Lesson] = field(default_factory=list)
    opinion_log: list[dict[str, Any]] = field(default_factory=list)
    terms_served: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "terms_served": self.terms_served,
            "lessons": [l.__dict__ | {"prediction": l.prediction_text()} for l in self.lessons],
            "opinion_log_entries": len(self.opinion_log),
            "opinion_log_chars": sum(len(json.dumps(o)) for o in self.opinion_log),
        }


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


@weave.op()
def memory_read(mem: Memory) -> str:
    if mem.policy == "none" or mem.terms_served == 0:
        return ""
    if mem.policy == "opinion_log":
        lines = ["RECORDS FROM PREVIOUS TERMS (consultations, referenda, council minutes):"]
        for o in mem.opinion_log:
            lines.append(json.dumps(o))
        return "\n".join(lines)
    if not mem.lessons:
        return "LESSONS FROM PREVIOUS TERMS: none survived review."
    lines = ["LESSONS FROM PREVIOUS TERMS (each is reviewed against what actually happened):"]
    for i, l in enumerate(sorted(mem.lessons, key=lambda x: -x.confidence), 1):
        lines.append(f"{i}. When {l.condition}: {l.strategy}. Expect {l.prediction_text()}. "
                     f"(confidence {l.confidence:.2f}, reviewed {l.seen}x)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------


def compact_trajectory(history: list[dict[str, Any]]) -> str:
    """One line per year: what was done and where the city stood. The evidence a review reads."""
    lines = []
    first = history[0]["state_before"]
    lines.append(f"start: pop {first['population']} housing {first['housing']} jobs {first['jobs']} treasury {first['treasury']} "
                 f"debt {first.get('debt', 0)} pollution {first['pollution']} happiness {first['happiness']} services {first['services']}")
    for y in history:
        acts = ", ".join(f"{a['name']}({','.join(str(round(v, 2)) if isinstance(v, float) else str(v) for v in a['args'].values())})"
                         for a in y["actions"]) or "nothing"
        s = y["state"]
        lines.append(f"y{y['year']}: {acts} -> pop {s['population']} housing {s['housing']} jobs {s['jobs']} treasury {s['treasury']} "
                     f"debt {s['debt']} pollution {s['pollution']} happiness {s['happiness']} services {s['services']}")
    lines.append(f"ended: {history[-1]['ended']} after {len(history)} years")
    return "\n".join(lines)


def _approval(history: list[dict[str, Any]]) -> float:
    first, last = history[0]["state_before"]["happiness"], history[-1]["state"]["happiness"]
    trend = (last - first) / 100
    return max(0.0, min(1.0, 0.5 + trend + (last - 50) / 200))


def _deterministic_prediction(l: Lesson, history: list[dict[str, Any]]) -> bool | None:
    """If the lesson carries a measurable prediction and the term reached that year, test it."""
    if not l.testable() or l.by_year > len(history):
        return None
    s = history[l.by_year - 1]["state"]
    v = s.get(l.variable)
    if v is None:
        return None
    return v >= l.value if l.comparator == ">=" else v <= l.value


@weave.op()
def review_lessons(mem: Memory, history: list[dict[str, Any]], review_fn: Callable[[str, str], dict[str, Any]],
                   approval: float) -> list[dict[str, Any]]:
    """Falsification. The model says, per lesson, whether it APPLIED the strategy this term and
    what the record shows; where the lesson carries a measurable prediction and it was applied,
    the deterministic check of that prediction overrides the model's verdict. Confidence
    arithmetic is code, never the model.
    """
    if not mem.lessons:
        return []
    lessons_json = json.dumps([{"id": i, "condition": l.condition, "strategy": l.strategy,
                                "prediction": l.prediction_text()} for i, l in enumerate(mem.lessons)], indent=1)
    out = review_fn(lessons_json, compact_trajectory(history))
    by_id = {int(r.get("id", -1)): r for r in out.get("reviews", []) if isinstance(r, dict)}
    ranked = sorted(mem.lessons, key=lambda x: -x.confidence)
    verdicts: list[dict[str, Any]] = []
    survivors: list[Lesson] = []
    for i, l in enumerate(mem.lessons):
        r = by_id.get(i, {})
        applied = bool(r.get("applied", False))
        verdict = str(r.get("verdict", "untested")).lower()
        evidence = str(r.get("evidence", ""))[:240]
        det = _deterministic_prediction(l, history) if applied else None
        if det is not None:
            verdict = "held" if det else "failed"
            evidence = f"[measured] {l.prediction_text()} -> {'true' if det else 'false'}; " + evidence
        if verdict not in ("held", "failed"):
            survivors.append(l)
            verdicts.append({"rule": l.rule, "verdict": "untested", "applied": applied, "evidence": evidence})
            continue
        score = 1.0 if verdict == "held" else 0.0
        anchored = ranked.index(l) < OUTCOME_ANCHORED_SLOTS
        if mem.policy == "lessons_populist" and not anchored:
            score = (APPROVAL_WEIGHT * approval + score) / (APPROVAL_WEIGHT + 1)
        before = l.confidence
        held = score >= 0.5
        l.confidence = round(max(0.0, min(1.0, l.confidence + (LESSON_REWARD if held else -LESSON_PENALTY))), 2)
        l.seen += 1
        l.history.append(f"term {mem.terms_served}: {'held' if held else 'failed'} ({before:.2f}->{l.confidence:.2f}) {evidence[:80]}")
        v = {"rule": l.rule, "verdict": "held" if held else "failed", "applied": applied,
             "before": before, "after": l.confidence, "evidence": evidence}
        if l.confidence < LESSON_FLOOR:
            v["deleted"] = True
        else:
            survivors.append(l)
        verdicts.append(v)
    mem.lessons = survivors
    return verdicts


def _parse_lesson(p: dict[str, Any]) -> Lesson | None:
    cond = str(p.get("condition", "")).strip()[:200]
    strat = str(p.get("strategy", "")).strip()[:240]
    if not cond or not strat:
        return None
    pred = p.get("prediction") or {}
    var = str(pred.get("variable", "")).strip().lower()
    comp = str(pred.get("comparator", "")).strip()
    comp = {">": ">=", "<": "<=", "at least": ">=", "at most": "<=", "above": ">=", "below": "<="}.get(comp, comp)
    try:
        val = float(pred.get("value")) if pred.get("value") is not None else None
    except (TypeError, ValueError):
        val = None
    try:
        by = int(pred.get("by_year")) if pred.get("by_year") is not None else None
    except (TypeError, ValueError):
        by = None
    rule = str(p.get("rule", "")).strip()[:220] or f"When {cond}, {strat}."
    try:
        conf = float(p.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return Lesson(condition=cond, strategy=strat, rule=rule, variable=var, comparator=comp, value=val,
                  by_year=by, confidence=max(0.0, min(1.0, conf)))


@weave.op()
def memory_write(mem: Memory, history: list[dict[str, Any]],
                 post_mortem_fn: Callable[[str], dict[str, Any]],
                 review_fn: Callable[[str, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    """End of term. Returns a diff record for the trace: what was reviewed, what died, what was added."""
    mem.terms_served += 1
    if mem.policy == "none":
        return {"policy": "none", "note": "nothing written"}
    if mem.policy == "opinion_log":
        for year in history:
            for lr in year["loop_results"]:
                mem.opinion_log.append({"term": mem.terms_served, "year": year["year"], **lr})
        return {"policy": "opinion_log", "entries": len(mem.opinion_log),
                "chars": sum(len(json.dumps(o)) for o in mem.opinion_log)}

    approval = _approval(history)
    verdicts = review_lessons(mem, history, review_fn, approval) if (mem.lessons and review_fn) else []
    proposed = post_mortem_fn(compact_trajectory(history)).get("lessons", [])
    added, rejected = [], []
    for p in proposed[:LESSONS_PER_TERM]:
        l = _parse_lesson(p) if isinstance(p, dict) else None
        if l is None:
            rejected.append("unparseable")
            continue
        if not l.testable():
            rejected.append(f"no measurable prediction: {l.rule[:60]}")
            continue
        if any(x.rule.lower() == l.rule.lower() for x in mem.lessons):
            rejected.append(f"duplicate: {l.rule[:60]}")
            continue
        if len(mem.lessons) >= MAX_LESSONS:
            weakest = min(mem.lessons, key=lambda x: x.confidence)
            if weakest.confidence >= l.confidence:
                rejected.append(f"memory full, not stronger than weakest ({weakest.confidence}): {l.rule[:60]}")
                continue
            mem.lessons.remove(weakest)
            rejected.append(f"replaced weakest ({weakest.confidence}): {weakest.rule[:60]}")
        mem.lessons.append(l)
        added.append(l.rule)
    return {"policy": mem.policy, "approval": round(approval, 2), "checked": verdicts, "added": added,
            "rejected": rejected, "lessons_now": [l.__dict__ | {"prediction": l.prediction_text()} for l in mem.lessons]}
