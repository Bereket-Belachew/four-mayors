"""Run the judges over an existing run file, in place.

    .venv/bin/python -m judge.rejudge runs/demo-debt-rules.jsonl [--claude] [--typesafe] [--force]

Adds `judge` (Claude) and `judge_typesafe` to every episode that lacks one. Writes to a temp
file and renames, so a crash never loses the run. Both judges are traced in Weave.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")
import weave  # noqa: E402

weave.init(os.getenv("WEAVE_PROJECT", "coreweave-hacks"))

from judge.judge import judge_episode  # noqa: E402
from judge.typesafe_judge import judge_episode_typesafe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--claude", action="store_true")
    ap.add_argument("--typesafe", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-judge even if a score is present")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if not (a.claude or a.typesafe):
        a.claude = a.typesafe = True
    path = Path(a.file)
    eps = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def work(ep: dict) -> dict:
        tag = f"{ep['mayor']} s{ep['seed']} t{ep['term'] + 1}"
        if a.claude and (a.force or "scores" not in (ep.get("judge") or {})):
            try:
                ep["judge"] = judge_episode(ep["history"], ep["ended"])
                print(f"  claude   {tag}: {ep['judge']['scores']['total']}", flush=True)
            except Exception as e:  # never lose the episode
                ep["judge"] = {"error": str(e)}; print(f"  claude   {tag}: ERROR {e}", file=sys.stderr, flush=True)
        if a.typesafe and (a.force or "scores" not in (ep.get("judge_typesafe") or {})):
            try:
                ep["judge_typesafe"] = judge_episode_typesafe(ep["history"], ep["ended"])
                print(f"  typesafe {tag}: {ep['judge_typesafe']['scores']['total']}", flush=True)
            except Exception as e:
                ep["judge_typesafe"] = {"error": str(e)}; print(f"  typesafe {tag}: ERROR {e}", file=sys.stderr, flush=True)
        return ep

    with ThreadPoolExecutor(a.workers) as ex:
        eps = list(ex.map(work, eps))
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(e) + "\n" for e in eps))
    tmp.replace(path)
    print(f"wrote {len(eps)} episodes -> {path}")


if __name__ == "__main__":
    main()
