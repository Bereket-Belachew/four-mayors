"""One harness, four configs.

Each year the mayor sees: persona + current state + this term's own history +
memory (per policy) + results of loop actions it requested. It returns up to
three actions. At the end of a term, memory_write runs the policy.

The rubric and the judge are never imported here (PLAN 1.3.3).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import weave
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mayors.llm import LLM, LLMConfig  # noqa: E402
from mayors.memory import Memory, memory_read, memory_write  # noqa: E402
from sim.world import LOOP_ACTIONS, WORLD_LEVERS, Action, new_world, step  # noqa: E402

CONFIG_DIR = Path(__file__).parent / "configs"


def load_config(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def _levers_doc() -> str:
    lines = []
    for n, spec in WORLD_LEVERS.items():
        lo, hi = spec["range"]
        lines.append(f"- {n}({spec['arg']}: {lo}..{hi}) cost {spec['cost']}/unit, takes effect in {spec['delay']} year(s)")
    return "\n".join(lines)


def _loop_doc(available: list[str]) -> str:
    if not available:
        return ""
    desc = {
        "consult_industrialist": "a forecast and advice from the industrial bloc",
        "consult_economist": "a forecast and advice from the finance bloc",
        "hold_referendum": "citizen approval % for a proposed lever (args: {proposal: lever_name})",
        "read_last_report": "last year's full list of consequences and their causes",
    }
    lines = ["INFORMATION ACTIONS (each uses one of your 3 slots this year; result arrives next year):"]
    for n in available:
        lines.append(f"- {n}: {desc[n]} (cost {LOOP_ACTIONS[n]['cost']})")
    return "\n".join(lines)


SYSTEM_TEMPLATE = """You are the mayor of a small city. {persona}

Each year you may take up to 3 actions. Choose from these levers:
{levers}

{loop_doc}

Respond with JSON only: {{"reasoning": "<2 sentences>", "actions": [{{"name": "...", "args": {{...}}}}]}}
"""

YEAR_TEMPLATE = """{memory}

TERM SO FAR (your decisions and what followed):
{term_history}

INFORMATION RECEIVED THIS YEAR:
{loop_results}

CURRENT STATE (json):
{state}

Year {year} of {horizon}. Decide."""

POST_MORTEM_TEMPLATE = """POST-MORTEM. Your term has ended. Below is what actually happened, with every change
attributed to the decision that caused it (the 'economy' entries are background drift).

{summary}

Write at most 4 lessons for your next term. Each lesson must be falsifiable: name the lever
it is about, the state variable it predicts, and the direction. Use exactly this JSON:
{{"lessons": [{{"when": "<condition on the city>", "did": "<what you did>", "outcome": "<what followed>",
"rule": "<one sentence rule>", "action": "<lever name or ''>", "variable": "<population|jobs|treasury|pollution|happiness|services or ''>",
"direction": "<up|down|''>", "confidence": <0..1>}}]}}"""


class Mayor:
    def __init__(self, name: str, llm: LLM | None = None):
        self.name = name
        self.cfg = load_config(name)
        self.llm = llm or LLM(LLMConfig())
        self.memory = Memory(policy=self.cfg["memory_policy"])
        self.loop_actions: list[str] = list(self.cfg.get("loop_actions", []))
        self.system = SYSTEM_TEMPLATE.format(
            persona=self.cfg["persona"].strip(),
            levers=_levers_doc(),
            loop_doc=_loop_doc(self.loop_actions) + ("\n" + self.cfg["loop_hint"].strip() if self.cfg.get("loop_hint") else ""),
        )

    # ----- one year ---------------------------------------------------------
    @weave.op()
    def decide_year(self, state: dict[str, Any], term_history: list[dict[str, Any]],
                    loop_results: list[dict[str, Any]], memory_text: str) -> dict[str, Any]:
        hist_lines = []
        for y in term_history[-8:]:  # keep the prompt bounded
            acts = ", ".join(f"{a['name']}({json.dumps(a['args'])})" for a in y["actions"]) or "nothing"
            s = y["state"]
            hist_lines.append(f"year {y['year']}: did {acts} -> pop {s['population']}, jobs {s['jobs']}, "
                              f"treasury {s['treasury']}, pollution {s['pollution']}, happiness {s['happiness']}")
        user = YEAR_TEMPLATE.format(
            memory=memory_text,
            term_history="\n".join(hist_lines) or "(first year of the term)",
            loop_results="\n".join(json.dumps(r) for r in loop_results) or "(none)",
            state=json.dumps(state),
            year=state["year"] + 1,
            horizon=20,
        )
        out = self.llm.complete_json(self.system, user, purpose=f"{self.name}:decide")
        actions = []
        for a in out.get("actions", [])[:3]:
            if not isinstance(a, dict) or "name" not in a:
                continue
            if a["name"] in LOOP_ACTIONS and a["name"] not in self.loop_actions:
                continue  # not in this mayor's toolset
            actions.append(Action(str(a["name"]), dict(a.get("args") or {})))
        return {"actions": actions, "reasoning": out.get("reasoning", "")}

    # ----- one term ------------------------------------------------------------
    @weave.op()
    def serve_term(self, seed: int, term_index: int, scenario: str | None = None, params=None) -> dict[str, Any]:
        world = new_world(seed, scenario, params)
        memory_text = memory_read(self.memory)
        pending_loop_results: list[dict[str, Any]] = []
        tool_use: dict[str, int] = {}
        reasonings: list[str] = []
        while world.ended is None:
            decision = self.decide_year(world.state.public(world.params), world.history, pending_loop_results, memory_text)
            for a in decision["actions"]:
                tool_use[a.name] = tool_use.get(a.name, 0) + 1
            rec = step(world, decision["actions"])
            rec["reasoning"] = decision["reasoning"]
            reasonings.append(decision["reasoning"])
            pending_loop_results = rec["loop_results"]
        memory_before = self.memory.to_dict()
        diff = memory_write(self.memory, world.history, self._post_mortem)
        return {
            "mayor": self.name,
            "seed": seed,
            "term": term_index,
            "scenario": world.scenario,
            "ended": world.ended,
            "years": len(world.history),
            "final_state": world.state.public(world.params),
            "history": world.history,
            "tool_use": tool_use,
            "memory_before": memory_before,
            "memory_after": self.memory.to_dict(),
            "memory_diff": diff,
        }

    @weave.op()
    def _post_mortem(self, summary_json: str) -> dict[str, Any]:
        return self.llm.complete_json(self.system, POST_MORTEM_TEMPLATE.format(summary=summary_json),
                                      purpose=f"{self.name}:post_mortem")


def run_terms(name: str, seed: int, terms: int, llm: LLM | None = None) -> list[dict[str, Any]]:
    mayor = Mayor(name, llm)
    return [mayor.serve_term(seed, t) for t in range(terms)]


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("mayor", choices=["caesar", "bureaucrat", "reformer", "populist"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--terms", type=int, default=2)
    ap.add_argument("--no-weave", action="store_true")
    args = ap.parse_args()
    if not args.no_weave:
        import os
        weave.init(os.getenv("WEAVE_PROJECT", "coreweave-hacks"))
    for ep in run_terms(args.mayor, args.seed, args.terms):
        fs = ep["final_state"]
        print(f"{ep['mayor']} seed {ep['seed']} term {ep['term']}: {ep['ended']} after {ep['years']}y | "
              f"pop {fs['population']} jobs {fs['jobs']} treasury {fs['treasury']} pollution {fs['pollution']} "
              f"happiness {fs['happiness']} | tools {ep['tool_use']}")
        print("  memory:", json.dumps(ep["memory_diff"])[:400])
