"""Build the paper: web/paper.html, an essay with figures drawn from the real run file.

    .venv/bin/python scripts/paper.py

Every number and every figure in the page is computed here from runs/demo-science.jsonl and
web/data/world.json, so the text can never drift from the data. Prose lives in this file.
"""
from __future__ import annotations

import html
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/demo-science.jsonl"
WORLD = ROOT / "web/data/world.json"
OUT = ROOT / "web/paper.html"
ORDER = ["caesar", "bureaucrat", "reformer", "populist"]
NAMES = {"caesar": "Caesar", "bureaucrat": "the Bureaucrat", "reformer": "the Reformer", "populist": "the Populist"}
CAP = {"caesar": "Caesar", "bureaucrat": "The Bureaucrat", "reformer": "The Reformer", "populist": "The Populist"}
COLOR = {"caesar": "#1c1c1e", "bureaucrat": "#7c7c82", "reformer": "#0a5cff", "populist": "#c78500"}
END_COLOR = {"horizon": "#1f9d55", "bankruptcy": "#d23b3b", "revolt": "#c78500", "depopulation": "#7c7c82"}
CITY = {0: "the unemployment city", 1: "the smog city"}

eps = [json.loads(l) for l in RUN.read_text().splitlines() if l.strip()]
world = json.loads(WORLD.read_text())
E = lambda s: html.escape(str(s))


def by(m, s):
    return sorted([e for e in eps if e["mayor"] == m and e["seed"] == s], key=lambda e: e["term"])


def mean(xs):
    return sum(xs) / len(xs)


def corr(a, b):
    ma, mb = mean(a), mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


# ------------------------------------------------------------------ numbers the prose uses
agg = {m: {"f": [e["scoreboard"]["total"] for e in eps if e["mayor"] == m],
           "c": [e["judge"]["scores"]["total"] for e in eps if e["mayor"] == m],
           "t": [e["judge_typesafe"]["scores"]["total"] for e in eps if e["mayor"] == m],
           "ends": Counter(e["ended"] for e in eps if e["mayor"] == m)} for m in ORDER}
F = [e["scoreboard"]["total"] for e in eps]
C = [e["judge"]["scores"]["total"] for e in eps]
T = [e["judge_typesafe"]["scores"]["total"] for e in eps]
r_fc, r_ft, r_ct = corr(F, C), corr(F, T), corr(C, T)
conf = defaultdict(list)
for e in eps:
    for k, v in e["judge_typesafe"]["confidence"].items():
        conf[k].append(v)
conf_mean = {k: mean(v) for k, v in conf.items()}
tool = {m: Counter() for m in ORDER}
for e in eps:
    tool[e["mayor"]].update(e["tool_use"])
INFO = {"consult_industrialist", "consult_economist", "hold_referendum", "read_last_report"}
ref0 = by("reformer", 0)
bur0 = by("bureaucrat", 0)
ref1 = by("reformer", 1)
lessons_checked = {m: Counter() for m in ORDER}
for e in eps:
    for c in (e.get("memory_diff") or {}).get("checked") or []:
        lessons_checked[e["mayor"]][c["verdict"]] += 1
full_scores = [e["scoreboard"]["total"] for e in eps if e["ended"] == "horizon"]
early_scores = [e["scoreboard"]["total"] for e in eps if e["ended"] != "horizon"]
stubs = sum(1 for e in eps if e["years"] <= 2)
rank = lambda key: sorted(ORDER, key=lambda m: -mean(agg[m][key]))
same_rank = rank("f") == rank("c") == rank("t")

# the two lesson cards
failed_card = next(c for e in ref0 for c in (e.get("memory_diff") or {}).get("checked") or [] if c["verdict"] == "failed")
held_card = next(c for e in reversed(ref0) for c in (e.get("memory_diff") or {}).get("checked") or [] if c["verdict"] == "held")
verdict_ref3 = ref0[2]["judge"]["verdict"]
verdict_cae2 = by("caesar", 0)[1]["judge"]["verdict"]


# ------------------------------------------------------------------ figures (inline SVG)
def fig_scripts():
    """Three scripts on the same machine: population and treasury over the years."""
    ex = world["examples"]
    W, H = 760, 230
    panels = [("nothing", "Do nothing"), ("spam", "400 homes a year"), ("best", "Best random script")]
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    pw = 230
    for i, (k, label) in enumerate(panels):
        x0 = 10 + i * (pw + 30)
        e = ex[k]
        for j, (series, col, name) in enumerate([("population", "#1c1c1e", "people"), ("treasury", "#0a5cff", "treasury")]):
            s = e["series"][series]
            lo, hi = min(s), max(s)
            rng = (hi - lo) or 1
            y0, ph = 28 + j * 95, 70
            pts = " ".join(f"{x0 + (n / 19) * pw:.1f},{y0 + ph - (v - lo) / rng * ph:.1f}" for n, v in enumerate(s))
            out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
            out.append(f'<text x="{x0}" y="{y0 - 6}" class="lab">{name} · {s[0]:.0f} → {s[-1]:.0f}</text>')
        ended = "20 years" if e["ended"] == "horizon" else f'{e["ended"]} in year {e["years"]}'
        out.append(f'<text x="{x0}" y="{H - 8}" class="cap"><tspan font-weight="600">{E(label)}</tspan> · {ended} · score {e["score"]:.1f} of 60</text>')
    out.append("</svg>")
    return "".join(out)


def fig_loops():
    """Four rings: what crosses the term boundary."""
    W, H = 760, 250
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    labels = [("caesar", "no loop", "stateless policy", "nothing crosses"),
              ("bureaucrat", "half a loop", "supervised by advisers", "records written, never checked"),
              ("reformer", "closed loop", "reinforcement from outcomes", "lessons checked, wrong ones die"),
              ("populist", "closed loop, wrong reward", "reinforcement from approval", "lessons judged by applause")]
    for i, (m, kind, ml, note) in enumerate(labels):
        cx, cy, R = 95 + i * 190, 95, 58
        col = COLOR[m]
        # outer ring: full for reformer/populist, open for caesar, dashed segment for bureaucrat
        if m == "caesar":
            out.append(f'<path d="M{cx - R},{cy} A{R},{R} 0 1 1 {cx + R},{cy}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round"/>')
            out.append(f'<path d="M{cx + R},{cy} A{R},{R} 0 0 1 {cx - R},{cy}" fill="none" stroke="#d23b3b" stroke-width="3" stroke-dasharray="2 10" opacity=".7"/>')
        elif m == "bureaucrat":
            out.append(f'<path d="M{cx - R},{cy} A{R},{R} 0 1 1 {cx + R},{cy}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round"/>')
            out.append(f'<path d="M{cx + R},{cy} A{R},{R} 0 0 1 {cx},{cy + R}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round"/>')
            out.append(f'<path d="M{cx},{cy + R} A{R},{R} 0 0 1 {cx - R},{cy}" fill="none" stroke="#d23b3b" stroke-width="3" stroke-dasharray="2 10" opacity=".7"/>')
        else:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{col}" stroke-width="7"/>')
            gate = "#1f9d55" if m == "reformer" else "#c78500"
            out.append(f'<circle cx="{cx - R * 0.7:.0f}" cy="{cy + R * 0.7:.0f}" r="11" fill="#fbfaf7" stroke="{gate}" stroke-width="3"/>')
            out.append(f'<text x="{cx - R * 0.7:.0f}" y="{cy + R * 0.7 + 4:.0f}" text-anchor="middle" class="lab" fill="{gate}">✓</text>')
        out.append(f'<circle cx="{cx}" cy="{cy}" r="22" fill="none" stroke="{col}" stroke-width="3" opacity=".5"/>')
        out.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="lab">a year</text>')
        out.append(f'<text x="{cx}" y="{cy - R - 14}" text-anchor="middle" class="cap" font-weight="600">{E(CAP[m])}</text>')
        out.append(f'<text x="{cx}" y="{cy + R + 26}" text-anchor="middle" class="cap">{E(kind)}</text>')
        out.append(f'<text x="{cx}" y="{cy + R + 44}" text-anchor="middle" class="lab" fill="#4a4a4f">{E(ml)}</text>')
        out.append(f'<text x="{cx}" y="{cy + R + 60}" text-anchor="middle" class="lab" fill="#7c7c82">{E(note)}</text>')
    out.append("</svg>")
    return "".join(out)


def fig_terms():
    """Score across three terms, one panel per city, one line per mayor; early exits marked."""
    W, H = 760, 260
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    for pi, seed in enumerate((0, 1)):
        x0, pw, y0, ph = 50 + pi * 380, 280, 30, 170
        for g in (0, 20, 40, 60):
            y = y0 + ph - g / 60 * ph
            out.append(f'<line x1="{x0}" x2="{x0 + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e3dd"/><text x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end" class="lab">{g}</text>')
        for m in ORDER:
            row = by(m, seed)
            pts = [(x0 + (i / 2) * pw, y0 + ph - e["scoreboard"]["total"] / 60 * ph, e) for i, e in enumerate(row)]
            out.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)}" fill="none" stroke="{COLOR[m]}" stroke-width="2.5"/>')
            for x, y, e in pts:
                if e["ended"] != "horizon":
                    out.append(f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="#d23b3b" transform="rotate(45 {x:.1f} {y:.1f})"/>')
                else:
                    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{COLOR[m]}"/>')
            xl, yl, _ = pts[-1]
            out.append(f'<text x="{xl + 8:.1f}" y="{yl + 4:.1f}" class="lab" fill="{COLOR[m]}">{E(CAP[m])}</text>')
        for i in range(3):
            out.append(f'<text x="{x0 + (i / 2) * pw:.1f}" y="{y0 + ph + 18}" text-anchor="middle" class="lab">term {i + 1}</text>')
        out.append(f'<text x="{x0}" y="{H - 8}" class="cap" font-weight="600">{E(CITY[seed].capitalize())}</text>')
        out.append(f'<text x="{x0 + 160}" y="{H - 8}" class="lab" fill="#7c7c82">score of 60 · ◆ = ended in bankruptcy</text>')
    out.append("</svg>")
    return "".join(out)


def fig_fates():
    """Every term as a tile: colour is the ending, the number is the years survived."""
    W, H = 760, 150
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    for r, m in enumerate(ORDER):
        out.append(f'<text x="8" y="{38 + r * 28}" class="cap">{E(CAP[m])}</text>')
        i = 0
        for seed in (0, 1):
            for e in by(m, seed):
                x = 130 + i * 70 + (seed * 20)
                col = END_COLOR[e["ended"]]
                out.append(f'<rect x="{x}" y="{22 + r * 28}" width="62" height="22" rx="5" fill="{col}" opacity="{1 if e["ended"] == "horizon" else 0.85}"/>')
                out.append(f'<text x="{x + 31}" y="{37 + r * 28}" text-anchor="middle" class="lab" fill="#fff">{e["years"]}y · {e["scoreboard"]["total"]:.0f}</text>')
                i += 1
    out.append(f'<text x="130" y="14" class="lab" fill="#7c7c82">{E(CITY[0])}, terms 1–3</text><text x="360" y="14" class="lab" fill="#7c7c82">{E(CITY[1])}, terms 1–3</text>')
    out.append('<text x="8" y="142" class="lab" fill="#7c7c82">green: the full 20 years · red: bankruptcy · the number is years survived and the formula score</text>')
    out.append("</svg>")
    return "".join(out)


def fig_graders():
    """Formula vs the two judges, per term; and TypeSafe's confidence per criterion."""
    W, H = 760, 250
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    for pi, (key, label, r) in enumerate([("c", "Claude Sonnet 5", r_fc), ("t", "TypeSafe jev", r_ft)]):
        x0, s, y0 = 40 + pi * 250, 180, 30
        out.append(f'<line x1="{x0}" y1="{y0 + s}" x2="{x0 + s}" y2="{y0}" stroke="#e5e3dd"/>')
        out.append(f'<rect x="{x0}" y="{y0}" width="{s}" height="{s}" fill="none" stroke="#e5e3dd"/>')
        for e in eps:
            fx = e["scoreboard"]["total"] / 60 * s
            jy = (e["judge"]["scores"]["total"] if key == "c" else e["judge_typesafe"]["scores"]["total"]) / 60 * s
            out.append(f'<circle cx="{x0 + fx:.1f}" cy="{y0 + s - jy:.1f}" r="4" fill="{COLOR[e["mayor"]]}" opacity=".85"/>')
        out.append(f'<text x="{x0}" y="{y0 + s + 18}" class="lab">formula score →</text>')
        out.append(f'<text x="{x0}" y="{y0 - 10}" class="cap" font-weight="600">{E(label)} · r = {r:.2f}</text>')
        out.append(f'<text x="{x0 - 6}" y="{y0 + s / 2:.0f}" class="lab" text-anchor="end" transform="rotate(-90 {x0 - 6} {y0 + s / 2:.0f})">judge ↑</text>')
    # confidence bars
    x0, y0 = 560, 30
    out.append(f'<text x="{x0}" y="{y0 - 10}" class="cap" font-weight="600">TypeSafe confidence</text>')
    for i, k in enumerate(["prosperity", "housing", "fiscal", "environment", "wellbeing", "resilience"]):
        v = conf_mean[k]
        y = y0 + i * 30
        out.append(f'<text x="{x0}" y="{y + 12}" class="lab">{k}</text>')
        out.append(f'<rect x="{x0 + 82}" y="{y + 3}" width="100" height="10" rx="5" fill="#efede8"/><rect x="{x0 + 82}" y="{y + 3}" width="{v * 100:.0f}" height="10" rx="5" fill="{"#1f9d55" if v > .7 else "#c78500"}"/>')
        out.append(f'<text x="{x0 + 188}" y="{y + 12}" class="lab">{v:.2f}</text>')
    out.append("</svg>")
    return "".join(out)


def fig_tools():
    """What each mayor did with its actions: information actions vs levers."""
    W, H = 760, 170
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    mx = max(sum(c.values()) for c in tool.values())
    for r, m in enumerate(ORDER):
        c = tool[m]
        info = sum(v for k, v in c.items() if k in INFO)
        borrow = c.get("borrow", 0)
        levers = sum(c.values()) - info - borrow
        y = 22 + r * 34
        out.append(f'<text x="8" y="{y + 13}" class="cap">{E(CAP[m])}</text>')
        x = 130
        for val, col, name in [(info, "#6b4fbb", "asked"), (borrow, "#d23b3b", "borrowed"), (levers, COLOR[m], "other levers")]:
            w = val / mx * 560
            if val:
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="20" fill="{col}" opacity=".9"/>')
                if w > 34:
                    out.append(f'<text x="{x + w / 2:.1f}" y="{y + 14}" text-anchor="middle" class="lab" fill="#fff">{name} {val}</text>')
            x += w
    out.append(f'<text x="130" y="{H - 8}" class="lab" fill="#7c7c82">actions over six terms each · purple: consult, referendum, read last report · red: borrow</text>')
    out.append("</svg>")
    return "".join(out)


def fig_weave():
    W, H = 760, 150
    out = [f'<svg viewBox="0 0 {W} {H}" class="fig">']
    boxes = [(20, "serve_term", "one call per term"), (170, "memory_read", "what crossed in"), (320, "year_decide × 20", "state + memory → actions"),
             (490, "memory_write", "post-mortem → lessons"), (640, "review", "each lesson vs the record")]
    for x, name, sub in boxes:
        out.append(f'<rect x="{x}" y="40" width="112" height="46" rx="8" fill="#fff" stroke="#1c1c1e" stroke-width="1.5"/>')
        out.append(f'<text x="{x + 56}" y="59" text-anchor="middle" class="lab" font-family="ui-monospace, Menlo, monospace">{E(name)}</text>')
        out.append(f'<text x="{x + 56}" y="76" text-anchor="middle" class="lab" fill="#7c7c82">{E(sub)}</text>')
    for x in (132, 282, 432, 602):
        out.append(f'<line x1="{x}" y1="63" x2="{x + 38}" y2="63" stroke="#1c1c1e" stroke-width="1.5"/><polygon points="{x + 38},63 {x + 31},59 {x + 31},67" fill="#1c1c1e"/>')
    out.append('<rect x="320" y="104" width="112" height="34" rx="8" fill="#fff" stroke="#d23b3b" stroke-width="1.5"/><text x="376" y="126" text-anchor="middle" class="lab" font-family="ui-monospace, Menlo, monospace">judge_episode ×2</text>')
    out.append('<line x1="376" y1="86" x2="376" y2="104" stroke="#d23b3b" stroke-width="1.5" stroke-dasharray="3 3"/>')
    out.append('<text x="440" y="126" class="lab" fill="#7c7c82">Claude and TypeSafe, after the term, outside the mayor\'s reach</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ the essay
def table_means():
    rows = "".join(
        f"<tr><td>{E(CAP[m])}</td><td>{mean(agg[m]['f']):.1f}</td><td>{mean(agg[m]['c']):.1f}</td><td>{mean(agg[m]['t']):.1f}</td>"
        f"<td>{agg[m]['ends'].get('horizon', 0)} full · {agg[m]['ends'].get('bankruptcy', 0)} bankrupt</td>"
        f"<td>{lessons_checked[m]['held']} held · {lessons_checked[m]['failed']} failed</td></tr>" for m in ORDER)
    return f"""<table><thead><tr><th>mayor</th><th>formula</th><th>Claude judge</th><th>TypeSafe judge</th><th>six terms</th><th>lessons checked</th></tr></thead><tbody>{rows}</tbody></table>"""


def lesson_card(c, kind):
    ev = re.sub(r"^\[measured\]\s*", "", str(c.get("evidence", "")))
    ev = ev.split(";")[0][:220]
    return f"""<div class="lesson {kind}"><div class="k">{kind} · confidence {c['before']} → {c['after']}</div><div class="rule">“{E(c['rule'])}”</div><div class="ev">{E(ev)}</div></div>"""


sources = re.search(r"^## Sources\n(.*)", (ROOT / "docs/research/world-models.md").read_text(), flags=re.S | re.M).group(1).strip().splitlines()
src_items = "".join(f"<li>{re.sub(r'(https?://\\S+)', r'<a href=\"\\1\">\\1</a>', E(l.lstrip('- ')))}</li>" for l in sources if l.strip())

ref0_scores = " → ".join(f"{e['scoreboard']['total']:.1f}" for e in ref0)
bur0_scores = " → ".join(f"{e['scoreboard']['total']:.1f}" for e in bur0)
ref0_lessons = " then ".join(f"{sum(1 for c in (e.get('memory_diff') or {}).get('checked') or [] if c['verdict'] == 'held')} held, {sum(1 for c in (e.get('memory_diff') or {}).get('checked') or [] if c['verdict'] == 'failed')} failed" for e in ref0[1:])
bur_opinions = bur0[-1]["memory_after"].get("opinion_log_entries", 0)
cae_borrow = tool["caesar"]["borrow"]
pop_failed = lessons_checked["populist"]["failed"]
pop_held = lessons_checked["populist"]["held"]
ex = world["examples"]

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Four Mayors · What crosses the term boundary</title>
<link rel="stylesheet" href="theme.css">
<style>
  body {{ background: var(--bg); }}
  .paper {{ max-width: 720px; margin: 0 auto; padding: 56px 22px 120px; font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif; font-size: 18px; line-height: 1.6; color: var(--ink); }}
  .paper h1 {{ font-size: 44px; line-height: 1.08; letter-spacing: -.02em; margin: 0 0 14px; font-weight: 600; }}
  .paper .standfirst {{ font-size: 21px; line-height: 1.45; color: var(--ink-2); margin: 0 0 10px; }}
  .paper .byline {{ font-family: var(--font); font-size: 13px; color: var(--muted); margin: 0 0 44px; }}
  .paper h2 {{ font-size: 26px; letter-spacing: -.01em; margin: 56px 0 12px; font-weight: 600; }}
  .paper p {{ margin: 0 0 18px; }}
  .paper .pull {{ font-size: 24px; line-height: 1.35; color: var(--ink); border-left: 3px solid var(--ink); padding-left: 18px; margin: 30px 0; font-style: italic; }}
  figure {{ margin: 28px -40px; background: var(--surface); border-radius: var(--radius); padding: 18px 20px 12px; box-shadow: var(--shadow); }}
  @media (max-width: 860px) {{ figure {{ margin: 28px 0; }} }}
  svg.fig {{ width: 100%; height: auto; display: block; }}
  svg.fig text {{ font-family: var(--font); }} svg.fig .lab {{ font-size: 11px; fill: #1c1c1e; }} svg.fig .cap {{ font-size: 12.5px; fill: #1c1c1e; }}
  figcaption {{ font-family: var(--font); font-size: 13px; color: var(--ink-2); margin-top: 10px; line-height: 1.5; }} figcaption b {{ color: var(--ink); }}
  table {{ width: 100%; border-collapse: collapse; font-family: var(--font); font-size: 13.5px; margin: 8px 0 4px; }}
  th {{ text-align: left; color: var(--muted); font-weight: 500; padding: 8px 8px; border-bottom: 1px solid var(--hair-2); }} td {{ padding: 8px; border-bottom: 1px solid var(--hair); font-variant-numeric: tabular-nums; }}
  .lesson {{ background: #fff; border: 1px solid var(--hair); border-radius: 10px; padding: 12px 14px; margin: 10px 0; font-family: var(--font); font-size: 14px; }}
  .lesson .k {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }} .lesson .rule {{ font-size: 15.5px; margin: 4px 0; color: var(--ink); }} .lesson .ev {{ color: var(--ink-2); font-size: 12.5px; }}
  .lesson.failed {{ border-left: 3px solid var(--bad); }} .lesson.held {{ border-left: 3px solid var(--good); }}
  .verdict {{ font-family: var(--font); font-size: 14px; color: var(--ink-2); background: var(--surface-2); border-radius: 10px; padding: 12px 14px; margin: 10px 0; }} .verdict b {{ color: var(--ink); }}
  .aside {{ font-family: var(--font); font-size: 14px; color: var(--ink-2); background: var(--surface-2); border-radius: 10px; padding: 14px 16px; margin: 18px 0; }} .aside b {{ color: var(--ink); }}
  .paper code {{ font-size: 14px; }}
  .sources {{ font-family: var(--font); font-size: 12.5px; color: var(--ink-2); columns: 1; }} .sources li {{ margin: 0 0 6px; }} .sources a {{ color: var(--accent); word-break: break-all; }}
  .topbar {{ font-family: var(--font); font-size: 13px; display: flex; gap: 14px; padding: 12px 22px; border-bottom: 1px solid var(--hair); }} .topbar a {{ color: var(--ink-2); }}
</style></head><body>
<div class="topbar"><a href="city3d.html">← the city</a><a href="https://github.com/Bereket-Belachew/four-mayors">source</a><a href="https://wandb.ai/betab-belachew1-fana-ai/coreweave-hacks/weave">Weave traces</a><a href="../docs/WORLD-RULES.md">the rules</a><a href="../docs/research/world-models.md">the research</a></div>
<article class="paper">
<h1>What crosses the term boundary</h1>
<p class="standfirst">Four mayors run the same city, on the same model, from the same seed. They differ in one thing only: what they carry from one twenty-year term into the next. Here is what happened, how we measured it, and why the one who checked his own notes against the record was the only one whose city got better.</p>
<p class="byline">Four Mayors · CoreWeave Hacks, San Francisco, 12–13 September 2026 · built solo · every number on this page is computed from <code>runs/demo-science.jsonl</code> by <code>scripts/paper.py</code></p>

<p>Agents that run for a long time have a problem that agents answering one question do not. They have to decide what to remember. Remember everything and the memory becomes a landfill nobody reads. Remember nothing and every day is the first day. Remember only the lessons and you have to decide which lessons were true, which is the hard part.</p>
<p>We wanted to see this problem in the open, with the confounders removed. So we built a city that is a machine, gave it to four mayors who are the same language model with the same tools, and let only the memory design differ. The city is small enough to read and honest enough to punish. Twenty years is a term. Between terms, something crosses over, or does not. That crossing is the experiment.</p>

<h2>The world is a machine</h2>
<p>The city is seven numbers: people, homes, jobs, treasury, pollution, happiness and services, plus a debt. A mayor has eight levers: set the tax rate, build homes, build a factory, build a park, fund transit, fund services, subsidise business, borrow. One function steps the city forward a year. There is no model inside it. Given the same seed and the same actions, it produces the same city, byte for byte, on any machine; a test asserts this, and the World tab in the game shows the hash.</p>
<p>Consequences land late. Homes take a year, factories two. Every change to a number is recorded as an event that remembers which decision caused it and in what year. That log is what a mayor reads at the end of a term, and it is what the chronicler narrates.</p>
<figure>{fig_scripts()}<figcaption><b>Figure 1 · Three scripts on one machine.</b> Doing nothing for twenty years, building four hundred homes every year, and the best of four hundred random scripts. The housing trap is Jay Forrester's 1969 result reproduced from first principles: people pour in, jobs do not follow, the city is bankrupt in year {ex['spam']['years']} with the population near its peak. Same seed twice gives hash {ex['same_seed_twice']['hash']} both times.</figcaption></figure>
<p>Every rule was then checked against fifty-five years of published city models and the wellbeing literature, in a companion document written for non-economists. Some things we had right by instinct: the workforce is sixty percent of the population, which is the real figure; happiness has inertia; parks absorb pollution with diminishing returns. Some things we had wrong and fixed on the morning of the second day: a job now needs a worker before it pays tax, tax flight is a gentle slope rather than a cliff at thirty percent, taxes hurt mood only as far as they fail to buy services, and once a term a recession removes a tenth of the jobs, so that resilience has something to be resilient about. One exaggeration we kept on purpose and labelled: a park cleans far more air here than real trees do, because a lever that does nothing measurable is not a lever a game can use.</p>

<h2>Four ways to remember</h2>
<figure>{fig_loops()}<figcaption><b>Figure 2 · The inner ring is a year</b> and is identical for all four: read the state, decide up to three actions, live the consequences. <b>The outer ring is a term</b>, and it is where they differ. Caesar's does not close. The Bureaucrat's writes but never checks. The Reformer's closes through a gate. The Populist's closes through the same gate, but the gate listens to applause.</figcaption></figure>
<p><b>Caesar</b> consults no one and carries nothing. Every term begins as if it were his first. In machine-learning terms he is a stateless policy: the same model, prompted fresh, with no signal from the past reaching the present. He is the control.</p>
<p><b>The Bureaucrat</b> asks everyone, every year: the industrialist, the economist, last year's report. He files every opinion, {bur_opinions} of them by the end of his third term in the unemployment city, and reads the file at the start of each term. He learns the way a student learns from a textbook written by people with interests: the industrialist's forecast overstates jobs by a quarter and understates smoke by forty percent, on purpose, and nobody ever grades the textbook against what happened. This is supervised learning from labels no one verified. The labels are advice. The teachers are biased. The pile grows.</p>
<p><b>The Reformer</b> writes a different kind of note. At the end of a term he distils at most four lessons, and each one must carry a prediction: <i>when X, do Y, and expect this number to be on this side of this value by this year.</i> At the end of the next term, each lesson is checked against the record. A prediction that came true raises the lesson's confidence. One that failed lowers it, and a lesson that fails twice is deleted. This is the loop of reinforcement learning, and of science: act, measure, update your belief in proportion to the surprise. No weights change; the update is in the memory, and we can read every step of it.</p>
<p><b>The Populist</b> runs the Reformer's machinery with one substitution. When a lesson is reviewed, what happened to the city counts for a third and what the citizens thought of it counts for two thirds. It is the same loop with the reward swapped for approval: the shape of learning from human feedback, and the failure mode that comes with it. A lesson can be right about the world and die because people booed, or wrong and survive because they cheered.</p>
<div class="aside"><b>A caution about the analogies.</b> Nothing here fine-tunes a model. All four mayors are one frozen model; every difference is in what the prompt contains at the start of a term, and that is configuration, not code. The analogies are about where the learning signal comes from: nowhere, from advisers, from outcomes, from applause. That is also the honest description of most memory systems being bolted onto agents today.</div>

<h2>What happened</h2>
<p>Two cities with different opening problems, an unemployment city and a smog city. Three consecutive terms each, with the city persisting between terms: debt, smoke, factories and unpaid bills all carry over. Four mayors. Twenty-four terms. It is a small experiment, and we say so again at the end.</p>
<figure>{fig_terms()}<figcaption><b>Figure 3 · Score across three terms, per city.</b> A diamond is a term that ended in bankruptcy; the score keeps only the share of the term the city survived, so a collapse in year 11 keeps 55 percent and a two-year stub keeps 10. In the unemployment city the Reformer climbs {ref0_scores}. The Bureaucrat, with his growing file, falls {bur0_scores}.</figcaption></figure>
<p class="pull">The Reformer's lesson record across those two reviews reads {ref0_lessons}. The lessons that survived were the ones about the city; the one that died was about timing.</p>
<p>The unemployment city is the clean case. Caesar borrowed his way to a full first term, then inherited his own debt and went bankrupt in year 11 of the second, and the third term was over in two years. The Bureaucrat survived all three terms, and got worse each time: his answer to every problem was to consult, and his {tool['bureaucrat']['read_last_report']} readings of last year's report never told him that the economist's forecast was fifteen percent too rosy. The Reformer got better each term, and his third-term city is the best-scored term in the file.</p>
<p>The smog city is the hard case, and it humbled everyone. Six factories, no parks, pollution at seventy on day one. Three of the four survived their first term; the Populist did not. The Reformer then inherited three thousand of debt and went bankrupt in his second, and his one surviving lesson, about expanding housing before growth projects, held but could not save him. The Populist is the only mayor who improved in this city, from a fourteen-year bankruptcy to a full term, before falling again. Across both cities the Populist's lessons were checked {pop_failed + pop_held} times and failed {pop_failed}: he wrote true things about debt and then did what the referendum wanted.</p>
{table_means()}
<figure>{fig_fates()}<figcaption><b>Figure 4 · Every term in the file.</b> Full terms scored between {min(full_scores):.0f} and {max(full_scores):.0f}; terms that ended early scored between {min(early_scores):.0f} and {max(early_scores):.0f}. {stubs} of the 24 are two-year stubs: a term that inherits a treasury below minus three thousand is bankrupt before its mayor can act. That is realistic, and it is a limit of this run.</figcaption></figure>

<h2>The gate, in the mayor's own words</h2>
<p>Here are two of the Reformer's lessons from the unemployment city, with the check that was run on them. The evidence line is the measured record, not the model's opinion of itself.</p>
{lesson_card(failed_card, "failed")}
{lesson_card(held_card, "held")}
<p>The failed lesson is the interesting one. It is not wrong about the world; funding services is usually right. It was wrong about <i>when</i>: services did not reach 55 by year 3, because the mayor's own third year went to tax and housing instead. The gate does not care why. The confidence dropped from 0.85 to 0.55, and in the third term the lesson was not among the ones he acted on. That is a self-correction visible in a log, which is the thing we set out to build.</p>

<h2>Three graders, none of them the mayor</h2>
<p>The mayors are scored on six criteria: jobs, homes, money, air, mood and resilience, each out of ten. The rubric that defines them is hidden. A test asserts that no phrase from it appears in any mayor prompt, and the mayor code has no import path to the judge. A judged score is reported beside the deterministic score and is never summed into it. That last rule matters more than it sounds: the moment a model's opinion enters the reward path, the mayors start optimising for the opinion.</p>
<p>The first grader is a formula, the same six criteria written as arithmetic, reproducible to the decimal. The second is Claude Sonnet 5, a model from a different lab than the mayors, reading the whole trajectory against six paragraphs of prose and naming the decision that mattered most. The third is TypeSafe's System One, a machine-native evaluator: it does not generate text, it answers typed questions. Each criterion became a scored question with a six-rung legend from worst to best, and each answer comes back with a confidence.</p>
<figure>{fig_graders()}<figcaption><b>Figure 5 · Where the graders agree.</b> Each dot is one term. The formula and the Claude judge correlate at {r_fc:.2f}, the formula and TypeSafe at {r_ft:.2f}, the two judges with each other at {r_ct:.2f}. {"All three produce the same ranking of the four mayors." if same_rank else f"The formula and TypeSafe rank the Reformer first; the Claude judge puts the Bureaucrat a hair above him ({mean(agg['bureaucrat']['c']):.1f} to {mean(agg['reformer']['c']):.1f}), the one place the three disagree."} TypeSafe is confident about money, mood and resilience and unsure about jobs and homes, which are ratios the trajectory text does not spell out. Its doubt points at exactly the criteria a human would ask a clarifying question about.</figcaption></figure>
<div class="verdict"><b>The Claude judge on the Reformer's third term:</b> {E(verdict_ref3)}</div>
<div class="verdict"><b>The same judge on Caesar's second:</b> {E(verdict_cae2)}</div>

<h2>Every step is traced</h2>
<figure>{fig_weave()}<figcaption><b>Figure 6 · The trace tree in Weights &amp; Biases Weave.</b> One call per term, twenty decisions inside it, the memory read at the start and the write and review at the end, and the two judges after. A judge can open one trace and watch a lesson fail. The project is public: <a href="https://wandb.ai/betab-belachew1-fana-ai/coreweave-hacks/weave">wandb.ai/betab-belachew1-fana-ai/coreweave-hacks/weave</a>.</figcaption></figure>
<p>Everything that touches a model is a Weave op: the yearly decision with its full prompt and the JSON it returned, the memory read, the post-mortem, the review with each lesson's verdict and evidence, both judges, the characters citizens can talk to, and the narrator's voice lines. The run panel in the game starts a sweep and streams progress; each run lands in its own file. When something looked wrong, and several things did, the trace was where we found it: a Claude judge that spent its whole budget thinking and returned truncated JSON that parsed as zeros, and a Luna post-mortem that hit the output ceiling and killed a run.</p>
<figure>{fig_tools()}<figcaption><b>Figure 7 · What they did with their actions.</b> The Bureaucrat spent {sum(v for k, v in tool['bureaucrat'].items() if k in INFO)} of his actions asking. Caesar borrowed {cae_borrow} times across six terms and never asked anyone anything. The Reformer used the most levers of all and asked only {sum(v for k, v in tool['reformer'].items() if k in INFO)} times, mostly to read his own report.</figcaption></figure>

<h2>What we would not claim</h2>
<p>Twenty-four terms is a pilot, not a benchmark. The mayors are a stochastic model; a second sweep would move every number, and the ordering of the two middle mayors could flip. The smog city bankrupted a Reformer who had a true lesson in hand, which is a reminder that a good loop on a doomed inheritance is still doomed. Six of the terms are two-year stubs and teach nothing; a grace period for inherited debt is a one-line change we chose not to make on the day. The analogies to supervised learning and reinforcement learning are about the origin of the signal, not the mechanism. And the world, for all its grounding, is a toy: a park cleans too much air, and there is no land price.</p>
<p>What we would claim is narrower and, we think, more useful. In a deterministic world with a hidden rubric and graders that never touch the reward, the only mayor whose city improved across terms was the one whose memory could be wrong, and knew it. The one who remembered everything did worse each term. The one who remembered nothing never had a second term worth the name. And the one who let the crowd grade his lessons wrote true things about debt and then borrowed anyway.</p>
<p class="pull">The loop is not the memory. The loop is the check.</p>

<h2>Built with</h2>
<p>OpenAI GPT 5.6 Luna for all four mayors and the citizens. Claude Sonnet 5 as the first judge. TypeSafe AI System One (jev) as the second judge. Weights &amp; Biases Weave for every trace. OpenAI text-to-speech for the narrator. Three.js and Kenney's CC0 kits for the city. Plain Python, no framework, 22 tests. The rules in plain words are in <code>docs/WORLD-RULES.md</code>; the research comparison is in <code>docs/research/world-models.md</code>.</p>

<h2>Appendix · sources the world was checked against</h2>
<ul class="sources">{src_items}</ul>
</article></body></html>"""

OUT.write_text(page)
print(f"wrote {OUT.relative_to(ROOT)} · {len(re.sub(r'<[^>]+>', ' ', page).split())} words incl. sources")
print("means", {m: round(mean(agg[m]['f']), 1) for m in ORDER}, "corr", round(r_fc, 3), round(r_ft, 3), round(r_ct, 3), "same rank", same_rank)
