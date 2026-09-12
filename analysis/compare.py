import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import json
    from pathlib import Path
    from statistics import median
    return Path, json, median, mo


@app.cell
def _(mo):
    mo.md(
        """
        # Four Mayors — do the loops diverge?

        Same city, same model, same seed. Four mayors that differ only in how they close the loop
        between terms of office. This notebook reads `runs/runs.jsonl` and asks one question:
        **does the choice of loop change the city, across seeds, and by how much?**

        Numbers are the deterministic scoreboard (six criteria, 0–10 each, by formula). The LLM
        judge's score is shown beside it and is never summed into it.
        """
    )
    return


@app.cell
def _(Path, json, mo):
    default = Path("runs/runs.jsonl")
    upload = mo.ui.file(kind="area", filetypes=[".jsonl"], label="Drop runs.jsonl here (or it reads runs/runs.jsonl)")
    upload
    return default, upload


@app.cell
def _(default, json, upload):
    text = upload.value[0].contents.decode() if upload.value else (default.read_text() if default.exists() else "")
    episodes = [json.loads(l) for l in text.splitlines() if l.strip()]
    mayors = sorted({e["mayor"] for e in episodes}, key=["caesar", "bureaucrat", "reformer", "populist", "reformer_shuffled"].index if episodes else None)
    seeds = sorted({e["seed"] for e in episodes})
    terms = sorted({e["term"] for e in episodes})
    return episodes, mayors, seeds, terms


@app.cell
def _(episodes, mo, seeds, terms):
    mo.stop(not episodes, mo.md("**No episodes loaded yet.** Run `python runner.py` first."))
    term_pick = mo.ui.slider(start=min(terms), stop=max(terms), value=max(terms), label="term of office")
    mo.hstack([mo.md(f"**{len(episodes)} episodes**, seeds {seeds}, terms {terms}"), term_pick])
    return (term_pick,)


@app.cell
def _(episodes, mayors, median, mo, term_pick):
    rows = []
    for m in mayors:
        xs = sorted(e["scoreboard"]["total"] for e in episodes if e["mayor"] == m and e["term"] == term_pick.value)
        if not xs:
            continue
        judged = [e["judge"]["scores"]["total"] for e in episodes
                  if e["mayor"] == m and e["term"] == term_pick.value and isinstance(e.get("judge"), dict) and "scores" in e["judge"]]
        ended = [e["ended"] for e in episodes if e["mayor"] == m and e["term"] == term_pick.value]
        rows.append({
            "mayor": m, "n": len(xs), "min": xs[0], "median": round(median(xs), 1), "max": xs[-1],
            "judge median": round(median(judged), 1) if judged else None,
            "early exits": sum(1 for x in ended if x != "horizon"),
        })
    mo.md(f"## Scoreboard at term {term_pick.value} (min / median / max across seeds)")
    mo.ui.table(rows, selection=None)
    return (rows,)


@app.cell
def _(mo, rows):
    if len(rows) >= 2:
        spans = [(r["mayor"], r["min"], r["max"]) for r in rows]
        overlaps = []
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                a, b = spans[i], spans[j]
                if a[1] <= b[2] and b[1] <= a[2]:
                    overlaps.append(f"{a[0]} ↔ {b[0]}")
        verdict = ("**Distributions overlap** for: " + ", ".join(overlaps) + ". Say so plainly; do not quote a mean alone.") if overlaps else "**No overlap** between any two mayors' ranges at this term."
    else:
        verdict = ""
    mo.md(verdict)
    return


@app.cell
def _(episodes, mayors, mo, terms):
    mo.md("## Score by term, per mayor (does anything compound?)")
    import altair as alt
    import pandas as pd
    df = pd.DataFrame([{"mayor": e["mayor"], "term": e["term"], "seed": e["seed"], "score": e["scoreboard"]["total"]} for e in episodes])
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("term:O"), y=alt.Y("score:Q", scale=alt.Scale(zero=False)),
        color="mayor:N", detail="seed:N", opacity=alt.value(0.7),
    ).properties(height=260)
    mo.ui.altair_chart(chart)
    return


@app.cell
def _(episodes, mo, term_pick):
    mo.md("## Tool use per mayor at this term (does anyone stop consulting someone?)")
    tu = {}
    for e in episodes:
        if e["term"] != term_pick.value:
            continue
        for k, v in e.get("tool_use", {}).items():
            tu.setdefault(e["mayor"], {}).setdefault(k, 0)
            tu[e["mayor"]][k] += v
    mo.ui.table([{"mayor": m, **{k: v for k, v in sorted(d.items())}} for m, d in tu.items()], selection=None)
    return


@app.cell
def _(episodes, mo):
    mo.md("## Self-catches: lessons contradicted by the next term and downgraded or deleted")
    sc = []
    for e in episodes:
        for v in e.get("memory_diff", {}).get("checked", []):
            if v.get("verdict") == "failed":
                sc.append({"mayor": e["mayor"], "seed": e["seed"], "term": e["term"], "rule": v["rule"],
                           "before": v.get("before"), "after": v.get("after"), "deleted": v.get("deleted", False)})
    mo.ui.table(sc, selection=None) if sc else mo.md("_none yet_")
    return


if __name__ == "__main__":
    app.run()
