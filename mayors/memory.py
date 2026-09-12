"""Memory policies: what a mayor reads before a term and writes after it.

This is the experiment. The inner loop (within a term) is identical for every
mayor; only these policies differ. See PLAN.md 1.2.2.

  none            Caesar.      Nothing crosses a term boundary.
  opinion_log     Bureaucrat.  Raw loop-action outputs (forecasts, referenda),
                               appended forever. Opinions, never outcomes.
  lessons         Reformer.    Post-mortem over the term's cause-tagged Events ->
                               at most 7 lessons in a fixed shape. Each lesson is
                               checked against the next term's Events; wrong ->
                               confidence down or deleted. Bounded, falsifiable.
  lessons_populist Populist.   Same mechanism, but lessons are checked mostly
                               against citizen approval (2:1 over outcomes); two
                               slots stay outcome-anchored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import weave

MAX_LESSONS = 7
OUTCOME_ANCHORED_SLOTS = 2


@dataclass
class Lesson:
    when: str  # condition on the city, in words
    did: str  # the action taken
    outcome: str  # what the Events said happened
    rule: str  # the rule the mayor draws
    confidence: float = 0.5  # 0..1
    seen: int = 1
    variable: str = ""  # which state variable the rule predicts, if any
    direction: str = ""  # "up" | "down" | "" (what the rule predicts the variable does)
    action: str = ""  # which lever the rule is about, if any
    history: list[str] = field(default_factory=list)  # audit trail of checks


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
            "lessons": [l.__dict__ for l in self.lessons],
            "opinion_log_entries": len(self.opinion_log),
            "opinion_log_chars": sum(len(json.dumps(o)) for o in self.opinion_log),
        }


# ---------------------------------------------------------------------------
# READ: what goes into the prompt at the start of (and during) a term
# ---------------------------------------------------------------------------


@weave.op()
def memory_read(mem: Memory) -> str:
    """Render memory for the prompt. Returns '' for Caesar."""
    if mem.policy == "none" or mem.terms_served == 0:
        return ""
    if mem.policy == "opinion_log":
        # Everything anyone ever told this mayor, verbatim, oldest first. No outcomes.
        lines = ["RECORDS FROM PREVIOUS TERMS (consultations, referenda, council minutes):"]
        for o in mem.opinion_log:
            lines.append(json.dumps(o))
        return "\n".join(lines)
    # lessons / lessons_populist
    if not mem.lessons:
        return "LESSONS FROM PREVIOUS TERMS: none survived review."
    lines = ["LESSONS FROM PREVIOUS TERMS (each was checked against what actually happened):"]
    for i, l in enumerate(sorted(mem.lessons, key=lambda x: -x.confidence), 1):
        lines.append(
            f"{i}. When {l.when}, I {l.did}; {l.outcome}. Rule: {l.rule} "
            f"(confidence {l.confidence:.2f}, seen {l.seen}x)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WRITE: what happens at the end of a term
# ---------------------------------------------------------------------------


def _term_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Compress a term's Events into what a post-mortem needs: per action, what it caused."""
    by_action: dict[str, dict[str, float]] = {}
    for year in history:
        for e in year["events"]:
            if e["cause_action"] == "economy":
                continue
            by_action.setdefault(e["cause_action"], {}).setdefault(e["variable"], 0.0)
            by_action[e["cause_action"]][e["variable"]] += e["delta"]
    first, last = history[0]["state_before"], history[-1]["state"]
    trend = {k: round(last[k] - first[k], 1) for k in ("population", "jobs", "treasury", "pollution", "happiness", "services")}
    return {
        "years": len(history),
        "ended": history[-1]["ended"],
        "start": {k: first[k] for k in trend},
        "end": {k: last[k] for k in trend},
        "trend": trend,
        "caused_by_action": {a: {k: round(v, 1) for k, v in d.items()} for a, d in by_action.items()},
        "actions_taken": {a: sum(1 for y in history for x in y["actions"] if x["name"] == a)
                          for a in {x["name"] for y in history for x in y["actions"]}},
    }


def _approval(history: list[dict[str, Any]]) -> float:
    """Citizen approval for the Populist's checker: happiness trend + last-year level, 0..1."""
    first, last = history[0]["state_before"]["happiness"], history[-1]["state"]["happiness"]
    trend = (last - first) / 100
    return max(0.0, min(1.0, 0.5 + trend + (last - 50) / 200))


@weave.op()
def check_lessons(mem: Memory, summary: dict[str, Any], approval: float) -> list[dict[str, Any]]:
    """Falsification. For each lesson that predicts a variable's direction under an
    action, compare with what this term's Events say that action caused. Wrong ->
    confidence down; below 0.2 -> deleted. Right -> confidence up, seen+1.

    Populist twist: the verdict is blended 2:1 with citizen approval, except for
    the top OUTCOME_ANCHORED_SLOTS lessons by confidence, which stay outcome-only.
    """
    verdicts: list[dict[str, Any]] = []
    caused = summary["caused_by_action"]
    ranked = sorted(mem.lessons, key=lambda x: -x.confidence)
    survivors: list[Lesson] = []
    for idx, l in enumerate(mem.lessons):
        outcome_ok: bool | None = None
        if l.action in caused and l.variable in caused[l.action] and l.direction in ("up", "down"):
            delta = caused[l.action][l.variable]
            outcome_ok = (delta > 0) if l.direction == "up" else (delta < 0)
        if outcome_ok is None:
            survivors.append(l)  # untestable this term; keep
            verdicts.append({"rule": l.rule, "verdict": "untested"})
            continue
        score = 1.0 if outcome_ok else 0.0
        anchored = ranked.index(l) < OUTCOME_ANCHORED_SLOTS
        if mem.policy == "lessons_populist" and not anchored:
            score = (2 * approval + score) / 3
        before = l.confidence
        l.confidence = round(max(0.0, min(1.0, l.confidence + (0.25 if score >= 0.5 else -0.3))), 2)
        l.seen += 1
        l.history.append(f"term {mem.terms_served}: {'held' if score >= 0.5 else 'failed'} ({before:.2f}->{l.confidence:.2f})")
        v = {"rule": l.rule, "verdict": "held" if score >= 0.5 else "failed", "before": before, "after": l.confidence}
        if l.confidence < 0.2:
            v["deleted"] = True
        else:
            survivors.append(l)
        verdicts.append(v)
    mem.lessons = survivors
    return verdicts


@weave.op()
def memory_write(mem: Memory, history: list[dict[str, Any]], post_mortem_fn) -> dict[str, Any]:
    """End of term. `post_mortem_fn(summary_json) -> {"lessons": [...]}` calls the model.

    Returns a diff record for the trace: what was checked, what died, what was added.
    """
    mem.terms_served += 1
    if mem.policy == "none":
        return {"policy": "none", "note": "nothing written"}
    if mem.policy == "opinion_log":
        for year in history:
            for lr in year["loop_results"]:
                mem.opinion_log.append({"term": mem.terms_served, "year": year["year"], **lr})
        return {"policy": "opinion_log", "entries": len(mem.opinion_log), "chars": sum(len(json.dumps(o)) for o in mem.opinion_log)}

    summary = _term_summary(history)
    approval = _approval(history)
    verdicts = check_lessons(mem, summary, approval) if mem.lessons else []
    proposed = post_mortem_fn(json.dumps(summary, indent=1)).get("lessons", [])
    added = []
    for p in proposed:
        if len(mem.lessons) >= MAX_LESSONS:
            break
        l = Lesson(
            when=str(p.get("when", ""))[:160], did=str(p.get("did", ""))[:160],
            outcome=str(p.get("outcome", ""))[:160], rule=str(p.get("rule", ""))[:200],
            confidence=float(p.get("confidence", 0.5)),
            variable=str(p.get("variable", "")), direction=str(p.get("direction", "")),
            action=str(p.get("action", "")),
        )
        # de-duplicate on rule text
        if any(x.rule.lower() == l.rule.lower() for x in mem.lessons):
            continue
        mem.lessons.append(l)
        added.append(l.rule)
    return {"policy": mem.policy, "approval": round(approval, 2), "checked": verdicts, "added": added,
            "lessons_now": [l.__dict__ for l in mem.lessons]}
