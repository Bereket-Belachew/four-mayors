"""The judge never leaks into the mayors, and the scoreboard is not vacuous (PLAN 1.3.3-1.3.5)."""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judge.scoreboard import CRITERIA, score_trajectory  # noqa: E402
from mayors import harness  # noqa: E402
from sim.world import Action, run_script  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _mayor_prompt_text() -> str:
    """Everything a mayor could ever be shown: templates + all persona configs."""
    parts = [harness.SYSTEM_TEMPLATE, harness.YEAR_TEMPLATE, harness.POST_MORTEM_TEMPLATE]
    for cfg in (ROOT / "mayors" / "configs").glob("*.yaml"):
        parts.append(cfg.read_text())
    return "\n".join(parts).lower()


def test_no_rubric_phrase_appears_in_any_mayor_prompt():
    rubric = (ROOT / "judge" / "rubric.md").read_text().lower()
    # distinctive multi-word phrases from the rubric
    phrases = [p for p in re.findall(r"[a-z][a-z ]{18,}[a-z]", rubric) if "score" in p or "points" in p]
    assert phrases, "rubric should have scoring phrases to test against"
    prompt = _mayor_prompt_text()
    for p in phrases:
        assert p not in prompt, f"rubric phrase leaked into mayor prompt: {p!r}"


def test_mayors_package_never_imports_judge():
    for py in (ROOT / "mayors").glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert not n.startswith("judge"), f"{py.name} imports {n}"


def test_empty_trajectory_scores_zero():
    s = score_trajectory([], "none")
    assert s["total"] == 0.0 and all(s[c] == 0.0 for c in CRITERIA)


def test_do_nothing_scores_below_a_reasonable_mayor():
    nothing = run_script(0, [])
    reasonable = run_script(0, [[Action("fund_services", {"level": 1})] if i % 3 == 0
                                else [Action("build_park", {"count": 1})] if i % 4 == 2 else []
                                for i in range(20)])
    s0 = score_trajectory(nothing.history, nothing.ended)
    s1 = score_trajectory(reasonable.history, reasonable.ended)
    assert s1["total"] > s0["total"], (s0, s1)


def test_early_exit_caps_resilience():
    spam = [[Action("build_housing", {"units": 400})] for _ in range(20)]
    w = run_script(0, spam)
    assert w.ended != "horizon"
    assert score_trajectory(w.history, w.ended)["resilience"] <= 2.0
