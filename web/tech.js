// "How it works": a semi-screen overlay showing the engine, the loop, the models, the guards,
// and this episode's live memory data. Static structure + live numbers from window.currentEp().
(function () {
  const btn = document.createElement("button"); btn.id = "techBtn"; btn.textContent = "⚙ how it works"; btn.title = "the engine and the loop, with this run's live data";
  const header = document.querySelector("header"); if (header) header.appendChild(btn);
  const ov = document.createElement("div"); ov.id = "tech"; ov.innerHTML = `<div class="tech-inner"><button class="tech-close">✕</button><div class="tech-body"></div></div>`;
  document.body.appendChild(ov);
  const st = document.createElement("style");
  st.textContent = `
    #tech { position:fixed; inset:0; background:rgba(0,0,0,.6); display:none; z-index:30; align-items:center; justify-content:center; }
    #tech.open { display:flex; }
    .tech-inner { width:min(1180px, 94vw); height:min(88vh, 900px); background:#111318; border:1px solid #2a2f3a; border-radius:14px; overflow:auto; position:relative; color:#e8e8ea; font:13px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
    .tech-close { position:sticky; top:10px; float:right; margin:10px; background:#171a21; color:#e8e8ea; border:1px solid #2a2f3a; border-radius:6px; padding:4px 10px; cursor:pointer; z-index:2; }
    .tech-body { padding:20px 26px 30px; display:grid; grid-template-columns: 1.15fr .85fr; gap:18px 26px; }
    .tech-body h1 { grid-column:1/-1; margin:0 0 4px; font-size:20px; }
    .tech-body h1 small { color:#9aa0aa; font-weight:400; font-size:13px; margin-left:10px; }
    .tech-body h2 { margin:8px 0 6px; font-size:14px; color:#fbbf24; text-transform:uppercase; letter-spacing:.6px; }
    .tech-body p, .tech-body li { color:#c9ccd3; margin:4px 0; }
    .tech-body code { background:#0b0d12; border:1px solid #2a2f3a; border-radius:4px; padding:0 5px; color:#93c5fd; font-size:12px; }
    .loop { display:grid; grid-template-columns: repeat(5, 1fr); gap:8px; align-items:stretch; }
    .node { background:#171a21; border:1px solid #2a2f3a; border-radius:10px; padding:8px 10px; min-height:84px; position:relative; }
    .node b { display:block; font-size:12px; color:#e8e8ea; margin-bottom:3px; } .node span { color:#9aa0aa; font-size:11.5px; }
    .node.world { border-color:#4ade80; } .node.mayor { border-color:#60a5fa; } .node.memory { border-color:#fbbf24; } .node.judge { border-color:#f87171; }
    .node .arrow { position:absolute; right:-14px; top:38%; color:#9aa0aa; font-size:16px; }
    .back { grid-column:1/-1; text-align:center; color:#fbbf24; font-size:12px; margin-top:-2px; }
    .cast { display:grid; grid-template-columns: repeat(2, 1fr); gap:6px; }
    .cast div { background:#171a21; border:1px solid #2a2f3a; border-radius:8px; padding:6px 8px; font-size:12px; } .cast div small { color:#9aa0aa; display:block; }
    .live { background:#0f1115; border:1px solid #2a2f3a; border-radius:10px; padding:10px 12px; }
    .live .row { display:flex; justify-content:space-between; gap:10px; border-bottom:1px dashed #2a2f3a; padding:3px 0; } .live .row:last-child { border-bottom:none; }
    .live .k { color:#9aa0aa; } .live .v { color:#e8e8ea; text-align:right; }
    .lesson { border-left:3px solid #2a2f3a; padding:4px 8px; margin:4px 0; font-size:12px; } .lesson.held { border-color:#4ade80; } .lesson.failed { border-color:#f87171; } .lesson.new { border-color:#fbbf24; } .lesson small { color:#9aa0aa; display:block; }
    .guard { display:flex; gap:8px; align-items:flex-start; margin:5px 0; } .guard .ok { color:#4ade80; }
    .tech-links a { color:#93c5fd; margin-right:14px; }
  `;
  document.head.appendChild(st);
  const NAMES = window.MAYOR_NAMES || {};
  const POLICY = { none: "none: nothing crosses a term boundary", opinion_log: "opinion log: every consultation appended forever, never checked", lessons: "lessons: ≤7 conditional, predictive rules; reviewed against next term's record; wrong → confidence down / deleted", lessons_populist: "lessons, populist: same, but the verdict is blended 2:1 with citizen approval (two slots stay outcome-only)" };

  function render() {
    const ep = window.currentEp ? window.currentEp() : null;
    const body = ov.querySelector(".tech-body");
    const mem = ep?.memory_before, diff = ep?.memory_diff || {}, checked = diff.checked || [];
    const cnt = v => checked.filter(c => c.verdict === v).length;
    const tools = ep ? Object.entries(ep.tool_use || {}).sort((a, b) => b[1] - a[1]) : [];
    const loopTools = tools.filter(([k]) => /^(consult|hold_|read_)/.test(k)).reduce((a, [, v]) => a + v, 0);
    body.innerHTML = `
      <h1>How it works <small>same city, same model, same seed · the only variable is how the loop closes</small></h1>
      <div>
        <h2>The loop</h2>
        <div class="loop">
          <div class="node world"><b>World</b><span>deterministic sim, 7 numbers, 8 levers, 4 information actions. Same seed + same actions → byte-identical trajectory (tested). Every change is an <code>Event</code> with a cause and the year it was decided. Effects land late via a pending queue.</span><div class="arrow">→</div></div>
          <div class="node mayor"><b>Mayor · inner loop</b><span>each year: state + this term's own history + memory + consultations → ≤3 actions. One harness, four YAML configs. Model: <code>${(ep && ep.param_overrides && ep.param_overrides.model) || "GPT 5.6 Luna"}</code>, identical for all four.</span><div class="arrow">→</div></div>
          <div class="node world"><b>20 years</b><span>a term of office. Ends early on bankruptcy, depopulation, or revolt. The city <b>persists</b> into the next term: debt, smoke, land, all inherited.</span><div class="arrow">→</div></div>
          <div class="node memory"><b>Memory · outer loop</b><span>the experiment. Caesar writes nothing. The Bureaucrat files opinions. The Reformer writes ≤7 lessons: <i>when X, do Y, expect V ⋚ n by year k</i>. The Populist does the same but is judged by applause.</span><div class="arrow">→</div></div>
          <div class="node memory"><b>Review · falsification</b><span>next term's record is the evidence. Applied? Held or failed? Where a prediction is measurable, code checks it and overrides the model. Confidence arithmetic is code. Wrong lessons decay and die.</span></div>
          <div class="back">↩ back to the mayor for the next term, with the scarred city and the surviving lessons</div>
        </div>
        <h2>Outside the loop, on purpose</h2>
        <div class="loop" style="grid-template-columns:1fr 1fr">
          <div class="node judge"><b>Hidden rubric + Claude judge</b><span>six criteria, scored from the whole trajectory by a model from a <i>different lab</i> than the mayors. A test asserts no rubric phrase appears in any mayor prompt and <code>mayors/</code> never imports <code>judge/</code>.</span></div>
          <div class="node judge"><b>Deterministic scoreboard</b><span>the same six criteria by formula (fiscal = net worth). Reported <i>beside</i> the judge, never summed. A judged score never enters the reward path. Empty and do-nothing runs are scored as controls and must land in the bottom band.</span></div>
        </div>
        <h2>The cabinet: agents in every city</h2>
        <div class="cast">
          <div>🎩 The mayor <small>GPT 5.6 Luna · decides</small></div>
          <div>🏭 The industrialist <small>consultant · forecast biased +25% jobs, −40% pollution</small></div>
          <div>📈 The economist <small>consultant · forecast biased +15% treasury, ignores happiness</small></div>
          <div>🗳 The citizens <small>referendum · approval computed from happiness + lever popularity</small></div>
          <div>🧠 The reviewer <small>LLM · reads the record, verdicts per lesson, evidence quoted</small></div>
          <div>📜 The chronicler <small>template · narrates only from cause-tagged events</small></div>
          <div>⚖️ The judge <small>Claude · hidden rubric · different lab</small></div>
          <div>👩‍🏭🌿🛒 Ama, Dr. Nadia, Rosa, Bram <small>freeze-and-ask · answer in character from the live state</small></div>
        </div>
        <h2>Guards</h2>
        <div class="guard"><span class="ok">✓</span><span>Determinism: same seed + script → identical bytes, asserted in tests. Noise is re-seeded per year and term.</span></div>
        <div class="guard"><span class="ok">✓</span><span>Leak guard: rubric text never reaches a mayor; no import path from mayors to judge.</span></div>
        <div class="guard"><span class="ok">✓</span><span>Anti-vacuity: an empty trajectory and a do-nothing term both score in the bottom band.</span></div>
        <div class="guard"><span class="ok">✓</span><span>Lessons without a measurable prediction are rejected at write time. Memory is bounded (7) and replaces its weakest.</span></div>
        <div class="guard"><span class="ok">✓</span><span>Token-matched control available: the Reformer with its rules shuffled (<code>--shuffled</code>).</span></div>
        <div class="guard"><span class="ok">✓</span><span>Every model call, memory read/write, review, judge, and citizen answer is a Weave op.</span></div>
        <p class="tech-links" style="margin-top:10px"><a href="https://github.com/Bereket-Belachew/four-mayors" target="_blank">repo</a><a href="https://wandb.ai/betab-belachew1-fana-ai/coreweave-hacks/weave" target="_blank">Weave traces</a><a href="https://github.com/Bereket-Belachew/four-mayors/blob/master/docs/WORLD-RULES.md" target="_blank">every rule and number, in plain words</a></p>
      </div>
      <div>
        <h2>This run, live</h2>
        ${ep ? `<div class="live">
          <div class="row"><span class="k">mayor</span><span class="v">${NAMES[ep.mayor] || ep.mayor}</span></div>
          <div class="row"><span class="k">city · seed · term</span><span class="v">${ep.scenario} · ${ep.seed} · ${(ep.term ?? 0) + 1}${ep.inherited ? " (inherited)" : ""}</span></div>
          <div class="row"><span class="k">memory policy</span><span class="v" style="max-width:62%">${POLICY[mem?.policy] || mem?.policy || "—"}</span></div>
          <div class="row"><span class="k">carried in</span><span class="v">${mem?.policy === "opinion_log" ? `${mem.opinion_log_entries} records · ${Math.round((mem.opinion_log_chars || 0) / 1000)}k chars` : `${(mem?.lessons || []).length} lessons`}</span></div>
          <div class="row"><span class="k">reviewed this term</span><span class="v">held ${cnt("held")} · <span style="color:#f87171">failed ${cnt("failed")}</span> · untested ${cnt("untested")}</span></div>
          <div class="row"><span class="k">written · rejected</span><span class="v">${(diff.added || []).length} · ${(diff.rejected || []).length}</span></div>
          <div class="row"><span class="k">ended</span><span class="v">${ep.ended} after ${ep.years} years</span></div>
          <div class="row"><span class="k">scoreboard · judge</span><span class="v">${ep.scoreboard?.total ?? "—"} / 60 · ${ep.judge?.scores?.total ?? "not run"}</span></div>
          <div class="row"><span class="k">information actions</span><span class="v">${loopTools} of ${tools.reduce((a, [, v]) => a + v, 0)} actions</span></div>
          <div class="row"><span class="k">lever use</span><span class="v" style="max-width:62%">${tools.map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ") || "—"}</span></div>
        </div>
        <h2>Memory diff at the end of this term</h2>
        ${checked.map(c => `<div class="lesson ${c.verdict}">${c.rule}<small>${c.verdict}${c.applied ? " · applied" : ""}${c.before !== undefined ? ` · ${c.before} → ${c.after}` : ""}${c.deleted ? " · deleted" : ""}${c.evidence ? `<br>${String(c.evidence).replace(/</g, "&lt;").slice(0, 160)}` : ""}</small></div>`).join("") || "<p>no lessons to review yet</p>"}
        ${(diff.added || []).map(a => `<div class="lesson new">${a}<small>new this term</small></div>`).join("")}
        ${(diff.rejected || []).length ? `<p style="color:#9aa0aa;font-size:12px">rejected: ${diff.rejected.slice(0, 3).join(" · ")}</p>` : ""}` : "<p>load a run to see live data</p>"}
      </div>`;
  }
  btn.onclick = () => { render(); ov.classList.add("open"); };
  ov.querySelector(".tech-close").onclick = () => ov.classList.remove("open");
  ov.addEventListener("click", e => { if (e.target === ov) ov.classList.remove("open"); });
  addEventListener("keydown", e => { if (e.key === "Escape") ov.classList.remove("open"); });
})();
