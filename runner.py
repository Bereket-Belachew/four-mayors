"""Sweep runner: N seeds x mayors x T terms -> runs/runs.jsonl, one line per episode.

Each line carries: mayor, seed, term, ended, years, final_state, scoreboard (deterministic),
judge (LLM, optional), tool_use, memory_before/after/diff, and the full history for replay.
Resumable: episodes already present in runs.jsonl are skipped.

Also writes runs/selfcatch.json: every (mayor, seed, term, lesson) where a lesson lost
confidence or was deleted, for the demo (PLAN 1.4.4).

Controls (PLAN 1.3.4): --controls writes runs/controls/{empty,do_nothing}.json with
scoreboard + judge scores; both must land in the bottom band.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

import weave  # noqa: E402

from judge.scoreboard import score_trajectory  # noqa: E402
from mayors.harness import Mayor  # noqa: E402
from mayors.llm import LLM, LLMConfig  # noqa: E402
from sim.world import run_script  # noqa: E402

RUNS = Path("runs")
RUNS_FILE = RUNS / "runs.jsonl"
MAYORS = ["caesar", "bureaucrat", "reformer", "populist"]


def _existing() -> set[tuple[str, int, int]]:
    if not RUNS_FILE.exists():
        return set()
    seen = set()
    for line in RUNS_FILE.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            seen.add((r["mayor"], r["seed"], r["term"]))
    return seen


def _shuffle_lessons(mayor: Mayor, seed: int) -> None:
    """Token-matched control (PLAN 1.4.3): same memory size, lessons permuted so the
    'when/did/outcome' no longer match the 'rule'."""
    ls = mayor.memory.lessons
    if len(ls) < 2:
        return
    rng = random.Random(seed * 1000 + mayor.memory.terms_served)
    rules = [l.rule for l in ls]
    rng.shuffle(rules)
    for l, r in zip(ls, rules):
        l.rule = r


def run_mayor(name: str, seed: int, terms: int, judge: bool, shuffled: bool,
              scenario: str | None = None, params=None, progress=None) -> list[dict[str, Any]]:
    label = name + ("_shuffled" if shuffled else "")
    mayor = Mayor(name, LLM(LLMConfig()))
    out = []
    for t in range(terms):
        if shuffled:
            _shuffle_lessons(mayor, seed)
        ep = mayor.serve_term(seed, t, scenario, params,
                              on_year=(lambda y, st, _t=t: progress(name, seed, _t, y, st)) if progress else None)
        ep["mayor"] = label
        ep["param_overrides"] = {k: getattr(params, k) for k in vars(params)} if params else {}
        ep["scoreboard"] = score_trajectory(ep["history"], ep["ended"])
        ep["scoreboard_by_year"] = [score_trajectory(ep["history"][:i], ep["ended"] if i == len(ep["history"]) else "running")
                                    for i in range(1, len(ep["history"]) + 1)]
        if judge:
            from judge.judge import judge_episode

            try:
                ep["judge"] = judge_episode(ep["history"], ep["ended"])
            except Exception as e:  # judge failure must not lose the episode
                ep["judge"] = {"error": str(e)}
        out.append(ep)
    return out


def self_catches(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for ep in episodes:
        for v in ep.get("memory_diff", {}).get("checked", []):
            if v.get("verdict") == "failed":
                found.append({"mayor": ep["mayor"], "seed": ep["seed"], "term": ep["term"],
                              "rule": v["rule"], "before": v.get("before"), "after": v.get("after"),
                              "deleted": v.get("deleted", False)})
    return found


def spread_report(episodes: list[dict[str, Any]]) -> str:
    by: dict[tuple[str, int], list[float]] = {}
    for ep in episodes:
        by.setdefault((ep["mayor"], ep["term"]), []).append(ep["scoreboard"]["total"])
    lines = [f"{'mayor':<20}{'term':>5}{'n':>3}{'min':>7}{'median':>8}{'max':>7}"]
    for (m, t), xs in sorted(by.items()):
        xs.sort()
        med = xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
        lines.append(f"{m:<20}{t:>5}{len(xs):>3}{xs[0]:>7.1f}{med:>8.1f}{xs[-1]:>7.1f}")
    return "\n".join(lines)


def write_controls(judge: bool) -> None:
    (RUNS / "controls").mkdir(parents=True, exist_ok=True)
    empty = {"name": "empty", "history": [], "ended": "none"}
    w = run_script(0, [])
    nothing = {"name": "do_nothing", "history": w.history, "ended": w.ended}
    for c in (empty, nothing):
        c["scoreboard"] = score_trajectory(c["history"], c["ended"])
        if judge:
            from judge.judge import judge_episode

            c["judge"] = judge_episode(c["history"], c["ended"])
        (RUNS / "controls" / f"{c['name']}.json").write_text(json.dumps(c, indent=1))
        print(f"control {c['name']}: scoreboard {c['scoreboard']['total']}"
              + (f", judge {c['judge']['scores']['total']}" if judge else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mayors", nargs="+", default=MAYORS)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--terms", type=int, default=3)
    ap.add_argument("--judge", action="store_true", help="also run the LLM judge (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--shuffled", action="store_true", help="add the reformer_shuffled control arm")
    ap.add_argument("--controls", action="store_true", help="write runs/controls/*.json")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-weave", action="store_true")
    ap.add_argument("--hard-starts", action="store_true",
                    help="each seed opens on a different crisis (sim/params.py SCENARIOS)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a sim parameter, e.g. --set park_mode=absorb --set land_enabled=true")
    args = ap.parse_args()
    from sim.params import DEFAULT
    overrides = {}
    for kv in args.set:
        k, v = kv.split("=", 1)
        cur = getattr(DEFAULT, k)
        if isinstance(cur, bool):
            v = v.lower() in ("1", "true", "yes")
        elif isinstance(cur, int):
            v = int(v)
        elif isinstance(cur, float):
            v = float(v)
        overrides[k] = v
    params = DEFAULT.with_(**overrides) if overrides else None
    if overrides:
        print("param overrides:", overrides)
    from sim.params import scenario_for
    scen = (lambda s: scenario_for(s)) if args.hard_starts else (lambda s: None)

    if not args.no_weave:
        weave.init(os.getenv("WEAVE_PROJECT", "coreweave-hacks"))
    RUNS.mkdir(exist_ok=True)
    if args.controls:
        write_controls(args.judge)

    done = _existing()
    jobs = [(m, s, False) for m in args.mayors for s in range(args.seeds)]
    if args.shuffled:
        jobs += [("reformer", s, True) for s in range(args.seeds)]
    jobs = [(m, s, sh) for m, s, sh in jobs
            if not all((m + ("_shuffled" if sh else ""), s, t) in done for t in range(args.terms))]
    print(f"{len(jobs)} mayor x seed jobs, {args.terms} terms each, provider={os.getenv('MAYOR_PROVIDER', 'mock')}")

    episodes: list[dict[str, Any]] = []
    with RUNS_FILE.open("a") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_mayor, m, s, args.terms, args.judge, sh, scen(s), params): (m, s, sh) for m, s, sh in jobs}
        for fut in as_completed(futs):
            m, s, sh = futs[fut]
            try:
                eps = fut.result()
            except Exception as e:
                print(f"FAILED {m} seed {s}: {e}")
                continue
            for ep in eps:
                f.write(json.dumps(ep) + "\n")
                f.flush()
                episodes.append(ep)
                fs = ep["final_state"]
                print(f"{ep['mayor']:<18} seed {s} [{ep.get('scenario','default')}] term {ep['term']}: {ep['ended']:<12} score {ep['scoreboard']['total']:>5.1f} "
                      f"| pop {fs['population']} jobs {fs['jobs']} $ {fs['treasury']} pol {fs['pollution']} happy {fs['happiness']}")

    # include earlier lines for the report
    all_eps = [json.loads(l) for l in RUNS_FILE.read_text().splitlines() if l.strip()]
    sc = self_catches(all_eps)
    (RUNS / "selfcatch.json").write_text(json.dumps(sc, indent=1))
    print(f"\nself-catches found: {len(sc)}")
    print(spread_report(all_eps))


if __name__ == "__main__":
    main()
