// The explain drawer: a living memory graph in the corner; click it and half the page opens with
// four tabs — Agent, Loop, World, Judges. Everything is drawn from the loaded run, never mocked.
(function () {
  const NAMES = window.MAYOR_NAMES || { caesar: "Caesar", bureaucrat: "The Bureaucrat", reformer: "The Reformer", populist: "The Populist" };
  const PORTRAIT = { caesar: "character-a", bureaucrat: "character-h", reformer: "character-e", populist: "character-m", reformer_shuffled: "character-e" };
  const POLICY = { none: "none", opinion_log: "a log of opinions", lessons: "falsifiable lessons", lessons_populist: "lessons, judged by applause" };
  const LEVERS = [["set_tax", "set tax", "💰"], ["build_housing", "build housing", "🏠"], ["build_factory", "build factory", "🏭"], ["build_park", "build park", "🌳"], ["fund_transit", "fund transit", "🚌"], ["fund_services", "fund services", "🏥"], ["subsidize_business", "subsidize business", "🏪"], ["borrow", "borrow", "🏦"]];
  const INFO = [["consult_industrialist", "consult industrialist", "🏭💬"], ["consult_economist", "consult economist", "📈💬"], ["hold_referendum", "hold referendum", "🗳"], ["read_last_report", "read last report", "📜"]];
  const TOOLSET = { caesar: [], bureaucrat: INFO.map(i => i[0]), reformer: INFO.map(i => i[0]), populist: INFO.map(i => i[0]), reformer_shuffled: INFO.map(i => i[0]) };
  const WHY = { caesar: "Caesar consults no one. This action is not in his toolset.", bureaucrat: "", reformer: "", populist: "" };

  // ---------- DOM ----------
  const game = document.getElementById("game"); if (!game) return;
  const corner = document.createElement("div"); corner.id = "memgraph"; corner.innerHTML = `<canvas></canvas><div class="mg-cap"><b>memory</b><span></span></div>`; corner.title = "the mayor's memory as a graph — click to open how it works";
  game.appendChild(corner);
  const drawer = document.createElement("div"); drawer.id = "explain";
  drawer.innerHTML = `<div class="ex-inner">
    <div class="ex-head"><div class="ex-tabs"><button data-t="agent" class="on">Agent</button><button data-t="loop">Loop</button><button data-t="world">World</button><button data-t="judges">Judges</button></div><button class="ex-close">✕</button></div>
    <div class="ex-body"></div></div>`;
  document.body.appendChild(drawer);
  const st = document.createElement("style");
  st.textContent = `
    #memgraph { position:absolute; right:14px; top:14px; width:220px; height:150px; border-radius:14px; background:rgba(251,250,247,.9); box-shadow:var(--shadow); cursor:pointer; overflow:hidden; z-index:5; backdrop-filter:blur(8px); transition:transform .15s; }
    #memgraph:hover { transform:translateY(-1px); }
    #memgraph canvas { width:100%; height:100%; display:block; }
    #memgraph .mg-cap { position:absolute; left:10px; bottom:6px; font-size:11px; color:var(--muted); } #memgraph .mg-cap b { color:var(--ink); font-weight:600; margin-right:6px; }
    #explain { position:fixed; top:0; right:0; bottom:0; width:min(52vw, 900px); transform:translateX(105%); transition:transform .35s cubic-bezier(.2,.8,.2,1); z-index:40; }
    #explain.open { transform:none; }
    .ex-inner { height:100%; background:var(--surface); box-shadow:-20px 0 60px rgba(28,28,30,.15); display:flex; flex-direction:column; }
    .ex-head { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--hair); }
    .ex-tabs { display:inline-flex; background:var(--surface-2); border-radius:999px; padding:3px; gap:2px; }
    .ex-tabs button { border:none; background:transparent; border-radius:999px; padding:6px 14px; color:var(--ink-2); }
    .ex-tabs button.on { background:#fff; color:var(--ink); box-shadow:0 1px 2px rgba(28,28,30,.12); }
    .ex-close { margin-left:auto; border-radius:999px; }
    .ex-body { padding:18px 22px 30px; overflow:auto; flex:1; }
    .ex-body h2 { font-size:20px; margin:0 0 4px; letter-spacing:-.01em; } .ex-body .lead { color:var(--ink-2); margin:0 0 16px; font-size:14px; }
    .ex-body h3 { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; margin:22px 0 8px; font-weight:500; }
    /* agent */
    .radial { position:relative; width:100%; max-width:560px; aspect-ratio:1; margin:6px auto; }
    .radial .center { position:absolute; left:50%; top:50%; width:150px; height:150px; transform:translate(-50%,-50%); border-radius:50%; background:radial-gradient(#fff, var(--surface-2)); box-shadow:var(--shadow); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
    .radial .center img { width:88px; height:88px; object-fit:contain; } .radial .center b { font-size:13px; } .radial .center small { color:var(--muted); font-size:11px; }
    .act { position:absolute; width:104px; transform:translate(-50%,-50%); text-align:center; font-size:11.5px; color:var(--ink-2); }
    .act .ic { width:44px; height:44px; margin:0 auto 4px; border-radius:50%; background:#fff; box-shadow:var(--shadow); display:flex; align-items:center; justify-content:center; font-size:18px; position:relative; }
    .act .n { position:absolute; right:-4px; top:-4px; background:var(--ink); color:#fff; border-radius:999px; font-size:10px; padding:1px 6px; font-variant-numeric:tabular-nums; }
    .act.info .ic { background:#f3efff; }
    .act.never { opacity:.38; } .act.never .ic { background:var(--surface-2); box-shadow:none; }
    .act.never .why { display:block; color:var(--bad); font-size:10.5px; margin-top:2px; }
    .act.unused .ic { box-shadow:none; background:var(--surface-2); }
    .legend { display:flex; gap:14px; color:var(--muted); font-size:12px; margin:8px 0 0; flex-wrap:wrap; }
    .legend i { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:-1px; }
    /* loop */
    .loopwrap { display:grid; grid-template-columns: 1fr 260px; gap:18px; align-items:start; }
    svg.loop { width:100%; height:auto; }
    svg.loop text { font-family:var(--font); }
    .stack { display:flex; flex-direction:column; gap:6px; }
    .stack div { background:#fff; border:1px solid var(--hair); border-radius:10px; padding:8px 10px; font-size:12px; color:var(--ink-2); }
    .stack div b { display:block; color:var(--ink); font-size:12.5px; } .stack div.off { opacity:.4; }
    .stack .weave { color:var(--accent); font-size:11px; }
    .lessoncard { background:#fff; border:1px solid var(--hair); border-radius:10px; padding:10px 12px; margin:6px 0; font-size:13px; }
    .lessoncard .k { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; } .lessoncard.failed { border-left:3px solid var(--bad); } .lessoncard.held { border-left:3px solid var(--good); } .lessoncard.new { border-left:3px solid var(--warn); }
    .lessoncard .ev { color:var(--ink-2); font-size:12px; margin-top:4px; }
    .conf { height:5px; background:var(--surface-2); border-radius:3px; margin-top:6px; overflow:hidden; } .conf i { display:block; height:100%; background:var(--ink); }
    /* world */
    .cards { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:8px; }
    .card { background:#fff; border:1px solid var(--hair); border-radius:10px; padding:10px 12px; font-size:12px; color:var(--ink-2); cursor:pointer; } .card:hover { border-color:var(--hair-2); } .card.on { box-shadow:0 0 0 1.5px var(--ink) inset; }
    .card b { display:block; color:var(--ink); font-size:13px; } .card .m { color:var(--muted); font-size:11px; }
    .law { background:var(--surface-2); border-radius:10px; padding:12px 14px; font-size:13px; color:var(--ink-2); margin-top:10px; min-height:52px; } .law b { color:var(--ink); }
    .spark { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; }
    .spark div { background:#fff; border:1px solid var(--hair); border-radius:10px; padding:10px; font-size:12px; color:var(--ink-2); } .spark svg { width:100%; height:64px; display:block; margin:4px 0; } .spark b { color:var(--ink); }
    .spark .sc { color:var(--muted); font-size:11px; }
    .pill { display:inline-block; background:var(--surface-2); border-radius:999px; padding:2px 10px; font-size:12px; color:var(--ink-2); margin:2px 4px 2px 0; }
    .pill.ok { background:#e6f4ea; color:var(--good); }
    /* judges */
    table.j { width:100%; border-collapse:collapse; font-size:12.5px; } table.j th { text-align:left; color:var(--muted); font-weight:500; padding:6px 8px; border-bottom:1px solid var(--hair); } table.j td { padding:6px 8px; border-bottom:1px solid var(--hair); font-variant-numeric:tabular-nums; }
  `;
  document.head.appendChild(st);
  const body = drawer.querySelector(".ex-body");
  let tab = "agent";
  drawer.querySelectorAll(".ex-tabs button").forEach(b => b.onclick = () => { tab = b.dataset.t; drawer.querySelectorAll(".ex-tabs button").forEach(x => x.classList.toggle("on", x === b)); render(); });
  drawer.querySelector(".ex-close").onclick = () => drawer.classList.remove("open");
  corner.onclick = () => { drawer.classList.add("open"); tab = "loop"; drawer.querySelectorAll(".ex-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "loop")); render(); };
  addEventListener("keydown", e => { if (e.key === "Escape") drawer.classList.remove("open"); });
  window.openExplain = t => { drawer.classList.add("open"); if (t) { tab = t; drawer.querySelectorAll(".ex-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === t)); } render(); };

  const ep = () => (window.currentEp ? window.currentEp() : null);
  const allEps = () => (window.allEpisodes ? window.allEpisodes() : []);
  const yr = () => (window.currentYear ? window.currentYear() : 0);
  // terms of the same mayor+seed up to and including the current one, oldest first
  function lineage(e) { return allEps().filter(p => p.mayor === e.mayor && p.seed === e.seed && p.term <= e.term).sort((a, b) => a.term - b.term); }

  // ---------- render ----------
  function render() {
    const e = ep(); if (!e) { body.innerHTML = "<p class='lead'>Load a run first.</p>"; return; }
    if (tab === "agent") renderAgent(e); else if (tab === "loop") renderLoop(e); else if (tab === "world") renderWorld(e); else renderJudges(e);
  }

  // ---------- AGENT: the mayor in a ring of actions ----------
  function renderAgent(e) {
    const tools = e.tool_use || {}, total = Object.values(tools).reduce((a, b) => a + b, 0);
    const set = TOOLSET[e.mayor] || [];
    const all = [...LEVERS.map(l => ({ ...{ k: l[0], label: l[1], ic: l[2] }, info: false })), ...INFO.map(l => ({ k: l[0], label: l[1], ic: l[2], info: true }))];
    const items = all.map((a, i) => {
      const n = tools[a.k] || 0; const never = a.info && !set.includes(a.k);
      const ang = -Math.PI / 2 + (i / all.length) * Math.PI * 2, R = 44;
      return `<div class="act ${a.info ? "info" : ""} ${never ? "never" : n ? "" : "unused"}" style="left:${50 + Math.cos(ang) * R}%; top:${50 + Math.sin(ang) * R}%">
        <div class="ic">${a.ic}${n ? `<span class="n">${n}</span>` : ""}</div>${a.label}${never ? `<span class="why">${WHY[e.mayor] || "not in this mayor's toolset"}</span>` : ""}</div>`;
    }).join("");
    body.innerHTML = `<h2>${NAMES[e.mayor] || e.mayor}</h2><p class="lead">${{ caesar: "Decides alone and fast. Consults no one. Carries nothing between terms.", bureaucrat: "Consults everyone, every year. Keeps every record. Checks none against outcomes.", reformer: "Writes falsifiable lessons from what actually happened. Reviews them next term. Drops the ones that fail.", populist: "The Reformer's method, judged by applause: lessons live or die by citizen approval." }[e.mayor] || ""}</p>
      <div class="radial"><div class="center"><img src="assets/kenney/kenney_blocky-characters/Previews/${PORTRAIT[e.mayor] || "character-a"}.png"><b>${NAMES[e.mayor] || e.mayor}</b><small>${total} actions this term</small></div>${items}</div>
      <div class="legend"><span><i style="background:#fff;box-shadow:var(--shadow)"></i>lever, used this term (count)</span><span><i style="background:#f3efff"></i>information action</span><span><i style="background:var(--surface-2)"></i>available, not used</span><span><i style="background:var(--surface-2);opacity:.4"></i>not in this mayor's toolset</span></div>
      <h3>How the same model becomes four mayors</h3>
      <p class="lead" style="font-size:13px">Every mayor runs the same model on the same prompt skeleton with the same eight levers. Two things differ, and both are configuration, not code: which information actions the toolset contains, and what is carried between terms — <b>${POLICY[e.memory_before?.policy] || "nothing"}</b>. The persona text is flavour only; it carries no strategy.</p>`;
  }

  // ---------- LOOP: two rings, a marble, a gate ----------
  function renderLoop(e) {
    const policy = e.memory_before?.policy || "none", y = yr(), years = e.years || 20;
    const diff = e.memory_diff || {}, checked = diff.checked || [], added = diff.added || [];
    const carried = e.memory_before?.lessons || [];
    // geometry
    const W = 560, H = 420, cx = 300, cy = 215, R = 165, r = 62;
    const pt = (rad, a) => [cx + Math.cos(a) * rad, cy + Math.sin(a) * rad];
    const A = { mayor: -Math.PI / 2, term_end: Math.PI * 0.05, memory: Math.PI * 0.45, review: Math.PI * 0.78, city: Math.PI * 1.15 };
    const arc = (a0, a1, rad, cls) => { const [x0, y0] = pt(rad, a0), [x1, y1] = pt(rad, a1); const large = (a1 - a0) % (2 * Math.PI) > Math.PI ? 1 : 0; return `<path d="M${x0},${y0} A${rad},${rad} 0 ${large} 1 ${x1},${y1}" class="${cls}" fill="none"/>`; };
    const node = (a, rad, label, sub, cls = "") => { const [x, yy] = pt(rad, a); return `<g class="node ${cls}"><circle cx="${x}" cy="${yy}" r="22" /><text x="${x}" y="${yy - 30}" text-anchor="middle" font-size="12" font-weight="600">${label}</text>${sub ? `<text x="${x}" y="${yy + 40}" text-anchor="middle" font-size="10.5" fill="#7c7c82">${sub}</text>` : ""}</g>`; };
    // outer ring: mayor -> (years) -> term end -> memory -> review -> city persists -> mayor
    const gapCaesar = policy === "none", gapBureau = policy === "opinion_log";
    const outer = [
      arc(A.mayor, A.term_end, R, "track"),
      arc(A.term_end, A.memory, R, gapCaesar ? "track missing" : "track"),
      arc(A.memory, A.review, R, (gapCaesar || gapBureau) ? "track missing" : "track"),
      arc(A.review, A.city, R, gapCaesar ? "track missing" : "track"),
      arc(A.city, A.mayor + 2 * Math.PI, R, "track"),
    ].join("");
    // inner ring (the year): decide -> act -> consequences
    const innerA = { decide: -Math.PI / 2, act: Math.PI / 6, cons: Math.PI * 5 / 6 };
    const inner = `<circle cx="${cx}" cy="${cy}" r="${r}" class="track thin" fill="none"/>` +
      [["decide", "decide", "state + history + memory + advice"], ["act", "act", "≤3 actions"], ["cons", "consequences", "cause-tagged, some land late"]].map(([k, l, s]) => { const [x, yy] = pt(r, innerA[k]); return `<g class="node small"><circle cx="${x}" cy="${yy}" r="12"/><text x="${x}" y="${yy + (k === "decide" ? -18 : 26)}" text-anchor="middle" font-size="10.5" font-weight="600">${l}</text></g>`; }).join("");
    // marble: on the inner ring by year fraction; term progress on the outer ring between mayor and term_end
    const frac = Math.min(1, y / years);
    const [mx, my] = pt(r, -Math.PI / 2 + frac * 2 * Math.PI);
    const [ox, oy] = pt(R, A.mayor + frac * ((A.term_end - A.mayor + 2 * Math.PI) % (2 * Math.PI)));
    const memLabel = policy === "none" ? "nothing written" : policy === "opinion_log" ? `${e.memory_after?.opinion_log_entries ?? "?"} records filed` : `${added.length} lessons written`;
    const revLabel = policy === "lessons" || policy === "lessons_populist" ? `${checked.filter(c => c.verdict === "held").length} held · ${checked.filter(c => c.verdict === "failed").length} failed` : gapBureau ? "never checked" : "no memory to review";
    const svg = `<svg class="loop" viewBox="0 0 ${W} ${H}">
      <style>.track{stroke:#1c1c1e;stroke-width:10;stroke-linecap:round;opacity:.9}.track.thin{stroke-width:6;opacity:.55}.track.missing{stroke:#d23b3b;stroke-dasharray:2 14;opacity:.7}.node circle{fill:#fff;stroke:#1c1c1e;stroke-width:2}.node.small circle{stroke-width:1.5}.node.gate circle{fill:#fbfaf7;stroke:#c78500}.marble{fill:#d23b3b}.marble2{fill:#0a5cff}</style>
      ${outer}${inner}
      ${node(A.mayor, R, "the mayor", `${NAMES[e.mayor] || e.mayor} · same model for all four`)}
      ${node(A.term_end, R, "term ends", `${years} years · city persists`)}
      ${node(A.memory, R, "memory written", memLabel, gapCaesar ? "faded" : "")}
      ${node(A.review, R, "check", revLabel, "gate")}
      ${node(A.city, R, "the city, scarred", `debt ${e.final_state?.debt ?? "?"} · pollution ${e.final_state?.pollution ?? "?"}`)}
      <circle cx="${mx}" cy="${my}" r="7" class="marble"/><circle cx="${ox}" cy="${oy}" r="7" class="marble2"/>
      <text x="${cx}" y="${cy + 4}" text-anchor="middle" font-size="13" font-weight="600">year ${y} of ${years}</text>
      ${gapCaesar ? `<text x="${pt(R + 28, Math.PI * 0.5)[0]}" y="${pt(R + 28, Math.PI * 0.5)[1]}" text-anchor="middle" font-size="11" fill="#d23b3b">nothing crosses the term boundary</text>` : ""}
      ${gapBureau ? `<text x="${pt(R + 28, Math.PI * 0.62)[0]}" y="${pt(R + 28, Math.PI * 0.62)[1]}" text-anchor="middle" font-size="11" fill="#d23b3b">records are never checked against outcomes</text>` : ""}
    </svg>`;
    const heard = (e.history || []).reduce((a, h) => a + (h.loop_results || []).length, 0);
    const stack = `<div class="stack">
      <div><b>What goes into the mayor's prompt each year</b></div>
      <div><b>The state</b>seven numbers plus unemployment, land, tier. <span class="weave">traced</span></div>
      <div><b>This term's own history</b>the last eight years: what he did, what followed.</div>
      <div class="${policy === "none" ? "off" : ""}"><b>Memory carried in</b>${policy === "none" ? "nothing — every term begins blank" : policy === "opinion_log" ? `${e.memory_before?.opinion_log_entries ?? 0} opinions, never checked` : `${carried.length} lessons with confidence scores`} <span class="weave">memory_read</span></div>
      <div class="${heard ? "" : "off"}"><b>Advice he asked for</b>${heard ? `${heard} consultations, referenda and reports this term` : "none — not in the toolset or not used"}</div>
      <div><b>Out: up to three actions</b>and one sentence of reasoning, as JSON. <span class="weave">year_decide → Weave</span></div>
      <div><b>At term end: post-mortem</b>${policy === "none" ? "skipped" : policy === "opinion_log" ? "records appended, nothing distilled" : "≤4 lessons: when X, do Y, expect V ⋚ n by year k"} <span class="weave">memory_write</span></div>
      <div><b>Next term end: review</b>${policy === "lessons" || policy === "lessons_populist" ? "each lesson checked against the record; wrong ones lose confidence or die" : "none"} <span class="weave">review</span></div>
    </div>`;
    const cards = [...checked.filter(c => c.verdict === "failed").map(c => `<div class="lessoncard failed"><div class="k">wrong · ${c.deleted ? "deleted" : "downgraded"}</div>${c.rule}<div class="ev">${String(c.evidence || "").replace(/^\[measured\]\s*/, "").slice(0, 160)}</div><div class="conf"><i style="width:${Math.round((c.after || 0) * 100)}%;background:var(--bad)"></i></div></div>`),
      ...checked.filter(c => c.verdict === "held").slice(0, 2).map(c => `<div class="lessoncard held"><div class="k">held · ${c.before} → ${c.after}</div>${c.rule}</div>`),
      ...added.slice(0, 2).map(a => `<div class="lessoncard new"><div class="k">written this term</div>${a}</div>`)].join("");
    body.innerHTML = `<h2>The loop</h2><p class="lead">Same city, same model, same seed. The inner ring is a year and is identical for every mayor. The outer ring is a term of office, and it is the experiment: what crosses from one term into the next. ${gapCaesar ? "Caesar's outer ring does not close." : gapBureau ? "The Bureaucrat writes but never checks." : "The Reformer's ring closes through a gate: lessons that fail the check die."}</p>
      <div class="loopwrap"><div>${svg}</div>${stack}</div>
      <h3>${cards ? "What the gate did at the end of this term" : "The gate"}</h3>${cards || `<p class="lead" style="font-size:13px">${policy === "none" ? "Nothing to check. Caesar begins every term as if it were his first." : policy === "opinion_log" ? "Nothing is ever checked. The pile of advice grows and contradicts itself." : "No lessons reviewed yet in this term."}</p>`}
      <h3>Traced in Weave</h3><p class="lead" style="font-size:13px">Every node on the ring is a traced call: <code>year_decide</code>, <code>memory_read</code>, <code>memory_write</code>, <code>review</code>, and the judge. A judge can open one trace and watch a lesson fail. <a href="https://wandb.ai/betab-belachew1-fana-ai/coreweave-hacks/weave" target="_blank">Open the project ↗</a></p>`;
  }

  // ---------- WORLD: the laws, and evidence they produce outcomes ----------
  let world = null, pick = null;
  async function renderWorld(e) {
    if (!world) { try { world = await (await fetch("data/world.json")).json(); } catch (err) { body.innerHTML = "<p class='lead'>world.json missing</p>"; return; } }
    const num = world.numbers.map(n => `<div class="card ${pick === n.k ? "on" : ""}" data-k="${n.k}"><b>${n.label}</b><span class="m">starts ${n.start} · ${n.range}</span></div>`).join("");
    const lev = world.levers.map(l => `<div class="card ${pick === l.k ? "on" : ""}" data-k="${l.k}"><b>${l.label}</b><span class="m">${l.cost} · lands ${l.lands}</span></div>`).join("");
    const info = world.info_actions.map(l => `<div class="card ${pick === l.k ? "on" : ""}" data-k="${l.k}"><b>${l.label}</b><span class="m">fee ${l.fee}</span></div>`).join("");
    const sel = [...world.numbers, ...world.levers, ...world.info_actions].find(x => x.k === pick);
    const law = sel ? `<b>${sel.label}.</b> ${sel.moves || sel.law}` : "Pick a number or a lever to read its law. Every number lives in one file, <code>sim/params.py</code>, and every rule is written in plain words in <code>docs/WORLD-RULES.md</code>.";
    const spark = (ex, key, color) => { const s = ex.series[key]; const min = Math.min(...s), max = Math.max(...s), rng = max - min || 1; const pts = s.map((v, i) => `${(i / (s.length - 1)) * 100},${64 - ((v - min) / rng) * 56 - 4}`).join(" "); return `<svg viewBox="0 0 100 64" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`; };
    const ex = world.examples;
    const sparks = ["nothing", "spam", "best"].map(k => `<div><b>${ex[k].label}</b>${spark(ex[k], "population", "#1c1c1e")}<span class="sc">population · ended ${ex[k].ended} after ${ex[k].years} years · score ${ex[k].score} of 60</span>${spark(ex[k], "treasury", "#0a5cff")}<span class="sc">treasury</span></div>`).join("");
    body.innerHTML = `<h2>The world is a machine</h2><p class="lead">Seven numbers, eight levers, four information actions, and one step function. Same seed and same actions give the same city, byte for byte, on any machine. Nothing in it is a model: the consultants' forecasts are computed by simulating a quiet year, then biased on purpose.</p>
      <h3>The seven numbers</h3><div class="cards">${num}</div>
      <h3>The eight levers · same for every mayor</h3><div class="cards">${lev}</div>
      <h3>Information actions · the toolset differs per mayor</h3><div class="cards">${info}</div>
      <div class="law">${law}</div>
      <h3>Evidence the laws bite</h3><div class="spark">${sparks}</div>
      <p class="lead" style="font-size:13px;margin-top:10px"><span class="pill ok">✓ same seed twice → identical hash ${ex.same_seed_twice.hash}</span><span class="pill">a term ends: ${world.ends.join(" · ")}</span></p>
      <h3>Consequences land late</h3><p class="lead" style="font-size:13px">Housing and parks take a year, factories and transit two. Every change to a number is an event that remembers the decision and the year that caused it. That log is what the Reformer reads at the end of a term, and what the chronicler narrates.</p>`;
    body.querySelectorAll(".card").forEach(c => c.onclick = () => { pick = c.dataset.k; renderWorld(e); });
  }

  // ---------- JUDGES ----------
  function renderJudges(e) {
    const sb = e.scoreboard || {}, j = e.judge && e.judge.scores, t = e.judge_typesafe && e.judge_typesafe.scores;
    const crit = ["prosperity", "housing", "fiscal", "environment", "wellbeing", "resilience"];
    const row = k => `<tr><td>${k}</td><td>${sb[k] ?? "—"}</td><td>${j ? j[k] : "—"}</td><td>${t ? t[k] : "—"}</td></tr>`;
    body.innerHTML = `<h2>Three graders, none of them the mayor</h2><p class="lead">The mayors never see the rubric: a test asserts no rubric phrase appears in any mayor prompt, and the mayor code has no import path to the judge. A judged score is reported beside the deterministic scoreboard and never summed into it. The judge is a model from a different lab than the mayors, on purpose.</p>
      <table class="j"><tr><th>criterion (0–10)</th><th>formula scoreboard</th><th>Claude judge</th><th>TypeSafe judge</th></tr>${crit.map(row).join("")}<tr><th>total</th><th>${sb.total ?? "—"}</th><th>${j ? j.total : "not run"}</th><th>${t ? t.total : "not run"}</th></tr></table>
      <h3>Why three</h3><p class="lead" style="font-size:13px">The formula is reproducible and is our opinion of what a good mayor is, written as arithmetic. The Claude judge reads the whole trajectory against six paragraphs of prose. TypeSafe is a machine-native evaluator: each criterion is a scored question with a legend, returned with a confidence. Where the three disagree is where the rubric is ambiguous, and where a judge favours a mayor's style is bias we can measure.</p>
      ${e.judge?.verdict ? `<h3>The Claude judge's verdict</h3><p class="lead" style="font-size:13px">${e.judge.verdict}</p>` : `<p class="lead" style="font-size:13px;color:var(--muted)">Judges have not run on this file yet. <code>python runner.py --judge</code> or the run panel.</p>`}`;
  }

  // ---------- corner graph: the memory as nodes ----------
  const cv = corner.querySelector("canvas"); const g = cv.getContext("2d");
  let nodes = [], links = [], lastKey = "";
  function buildGraph(e) {
    const line = lineage(e); const key = line.map(x => x.term).join(",") + "|" + e.mayor + e.seed; if (key === lastKey) return; lastKey = key;
    nodes = [{ id: "m", kind: "mayor", x: 110, y: 70, r: 9 }]; links = [];
    const policy = e.memory_before?.policy || "none";
    corner.querySelector(".mg-cap span").textContent = policy === "none" ? "nothing carried" : policy === "opinion_log" ? `${e.memory_before?.opinion_log_entries || 0} unchecked records` : `${(e.memory_before?.lessons || []).length} lessons carried`;
    let i = 0;
    for (const t of line) {
      const tn = { id: `t${t.term}`, kind: "term", x: 110 + Math.cos(i) * 40, y: 70 + Math.sin(i) * 30, r: 5, label: `term ${t.term + 1}` }; nodes.push(tn); links.push(["m", tn.id]);
      const d = t.memory_diff || {};
      if (policy === "opinion_log") { const n = Math.min(12, Math.round((t.memory_after?.opinion_log_entries || 0) / 8)); for (let k = 0; k < n; k++) { const id = `r${t.term}_${k}`; nodes.push({ id, kind: "record", x: tn.x + (Math.random() - .5) * 40, y: tn.y + (Math.random() - .5) * 40, r: 2.2 }); links.push([tn.id, id]); } }
      else if (policy !== "none") {
        for (const a of d.added || []) { const id = `l${t.term}_${a.slice(0, 20)}`; nodes.push({ id, kind: "new", x: tn.x + (Math.random() - .5) * 50, y: tn.y + (Math.random() - .5) * 50, r: 3.5, title: a }); links.push([tn.id, id]); }
        for (const c of d.checked || []) { const id = `c${t.term}_${(c.rule || "").slice(0, 20)}`; nodes.push({ id, kind: c.verdict === "failed" ? "failed" : c.verdict === "held" ? "held" : "untested", x: tn.x + (Math.random() - .5) * 50, y: tn.y + (Math.random() - .5) * 50, r: c.verdict === "failed" ? 4 : 3, title: c.rule }); links.push([tn.id, id]); }
      }
      i += 2.1;
    }
  }
  const COLOR = { mayor: "#1c1c1e", term: "#7c7c82", record: "#b8b6b0", new: "#c78500", held: "#1f9d55", failed: "#d23b3b", untested: "#9a9a92" };
  function stepGraph() {
    const W = cv.clientWidth, H = cv.clientHeight; if (cv.width !== W * 2) { cv.width = W * 2; cv.height = H * 2; }
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
    for (const n of nodes) { n.vx = (n.vx || 0) * 0.85; n.vy = (n.vy || 0) * 0.85; }
    for (let a = 0; a < nodes.length; a++) for (let b = a + 1; b < nodes.length; b++) { const p = nodes[a], q = nodes[b]; let dx = q.x - p.x, dy = q.y - p.y; let d2 = dx * dx + dy * dy + 0.01; const f = 90 / d2; dx *= f; dy *= f; p.vx -= dx; p.vy -= dy; q.vx += dx; q.vy += dy; }
    for (const [a, b] of links) { const p = byId[a], q = byId[b]; if (!p || !q) continue; const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, want = p.kind === "mayor" ? 34 : 16; const f = (d - want) * 0.02; p.vx += dx / d * f; p.vy += dy / d * f; q.vx -= dx / d * f; q.vy -= dy / d * f; }
    for (const n of nodes) { if (n.kind === "mayor") { n.x = W / 2; n.y = H / 2 - 6; continue; } n.vx += (W / 2 - n.x) * 0.002; n.vy += (H / 2 - n.y) * 0.002; n.x += n.vx; n.y += n.vy; n.x = Math.max(6, Math.min(W - 6, n.x)); n.y = Math.max(6, Math.min(H - 22, n.y)); }
    g.setTransform(2, 0, 0, 2, 0, 0); g.clearRect(0, 0, W, H);
    g.strokeStyle = "rgba(28,28,30,.18)"; g.lineWidth = 1;
    for (const [a, b] of links) { const p = byId[a], q = byId[b]; if (!p || !q) continue; g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke(); }
    for (const n of nodes) { g.beginPath(); g.arc(n.x, n.y, n.r, 0, Math.PI * 2); g.fillStyle = COLOR[n.kind] || "#999"; g.fill(); }
    if (nodes.length <= 1) { g.fillStyle = "#7c7c82"; g.font = "11px -apple-system, system-ui"; g.textAlign = "center"; g.fillText("no memory yet", W / 2, H / 2 + 24); }
  }
  function loop() { const e = ep(); if (e) { buildGraph(e); stepGraph(); } requestAnimationFrame(loop); }
  loop();
  // re-render the open drawer as the clock moves
  setInterval(() => { if (drawer.classList.contains("open") && tab === "loop") render(); }, 1000);
})();
