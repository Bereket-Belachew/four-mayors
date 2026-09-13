// Run panel: start a new run from the page and watch it progress; pick past run files.
// Talks to ask_server.py (localhost:8766): POST /run, GET /status, GET /runs.
(function () {
  const API = "http://localhost:8766";
  const header = document.querySelector("header"); if (!header) return;
  const btn = document.createElement("button"); btn.id = "runBtn"; btn.textContent = "▶ new run"; btn.className = "primary"; header.appendChild(btn);
  const sel = document.createElement("select"); sel.id = "runFile"; sel.title = "which run file to show"; header.appendChild(sel);
  const panel = document.createElement("div"); panel.id = "runpanel"; panel.hidden = true;
  panel.innerHTML = `
    <div class="rp-inner">
      <div class="rp-head"><b>New run</b><span class="rp-sub">the mayors run here, live, and land in the page when done (about 2 min per term)</span><button class="rp-close">✕</button></div>
      <div class="rp-row"><span>mayors</span><label><input type="checkbox" value="caesar" checked> Caesar</label><label><input type="checkbox" value="bureaucrat"> Bureaucrat</label><label><input type="checkbox" value="reformer" checked> Reformer</label><label><input type="checkbox" value="populist"> Populist</label></div>
      <div class="rp-row"><span>city</span>
        <label><input type="checkbox" name="seed" value="0" checked> unemployment</label><label><input type="checkbox" name="seed" value="1"> smog</label><label><input type="checkbox" name="seed" value="2"> debt</label><label><input type="checkbox" name="seed" value="3"> housing shortage</label></div>
      <div class="rp-row"><span>terms</span><select id="rp-terms"><option>1</option><option selected>2</option><option>3</option></select><span>label</span><input id="rp-label" placeholder="optional" style="width:140px"></div>
      <div class="rp-row"><button id="rp-start" class="primary">start</button><span id="rp-msg" class="rp-sub"></span></div>
      <div id="rp-progress"></div>
    </div>`;
  document.body.appendChild(panel);
  const st = document.createElement("style");
  st.textContent = `
    #runpanel { position:fixed; right:16px; top:64px; width:min(520px, 94vw); z-index:25; }
    .rp-inner { background:#111318; border:1px solid #2a2f3a; border-radius:12px; padding:12px 14px; color:#e8e8ea; font:13px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; box-shadow:0 20px 60px rgba(0,0,0,.6); }
    .rp-head { display:flex; gap:10px; align-items:baseline; margin-bottom:8px; } .rp-head .rp-close { margin-left:auto; }
    .rp-sub { color:#9aa0aa; font-size:12px; }
    .rp-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:6px 0; } .rp-row > span:first-child { color:#9aa0aa; width:52px; }
    .rp-row label { display:flex; gap:4px; align-items:center; }
    #rp-progress { margin-top:8px; display:flex; flex-direction:column; gap:4px; }
    .rp-job { background:#0f1115; border:1px solid #2a2f3a; border-radius:8px; padding:6px 8px; font-size:12px; }
    .rp-job .bar { height:6px; background:#0b0d12; border-radius:3px; overflow:hidden; margin-top:4px; } .rp-job .fill { height:100%; background:#2563eb; transition:width .5s; }
    .rp-job.done .fill { background:#4ade80; }
    #runFile { max-width:220px; }
  `;
  document.head.appendChild(st);

  async function refreshFiles(selectName) {
    try {
      const r = await fetch(`${API}/runs`); const j = await r.json();
      sel.innerHTML = j.runs.map(f => `<option value="${f.file}">${f.file.replace(/\.jsonl$/, "")} (${f.episodes})</option>`).join("");
      if (selectName) sel.value = selectName;
    } catch (e) { sel.innerHTML = `<option>runs.jsonl</option>`; sel.title = "ask_server.py is not running: python ask_server.py"; }
  }
  sel.onchange = () => { if (window.loadRunsFile) window.loadRunsFile(sel.value); };
  btn.onclick = () => { panel.hidden = !panel.hidden; };
  panel.querySelector(".rp-close").onclick = () => panel.hidden = true;

  const jobs = new Map();
  async function poll() {
    for (const [id, el] of jobs) {
      try {
        const j = await (await fetch(`${API}/status?id=${id}`)).json();
        const spec = j.spec, total = spec.mayors.length * spec.seeds.length * spec.terms * 20;
        let done = j.done.reduce((a, d) => a + 20, 0); // finished terms count 20 years
        for (const p of Object.values(j.progress)) { const finishedTermsForThis = j.done.filter(d => d.mayor === p.mayor && d.seed === p.seed).length; if (finishedTermsForThis <= p.term) done += p.year; }
        const pct = Math.min(100, Math.round(100 * done / Math.max(total, 1)));
        el.className = "rp-job" + (j.state === "done" ? " done" : "");
        el.innerHTML = `<div><b>${j.state}</b> · ${spec.mayors.join(", ")} · seeds ${spec.seeds.join(",")} · ${spec.terms} term(s) → <code>${j.file}</code></div>
          <div>${Object.values(j.progress).map(p => `${p.mayor} s${p.seed} t${p.term + 1} y${p.year} · pop ${p.state.population} $${p.state.treasury} debt ${p.state.debt} 😊${p.state.happiness}`).join("<br>")}</div>
          ${j.done.length ? `<div style="color:#9aa0aa">done: ${j.done.map(d => `${d.mayor} s${d.seed} t${d.term + 1} = ${d.score} (${d.ended})`).join(" · ")}</div>` : ""}
          ${j.errors.length ? `<div style="color:#f87171">${j.errors.join("<br>")}</div>` : ""}
          <div class="bar"><div class="fill" style="width:${pct}%"></div></div>`;
        if (j.state !== "running") { jobs.delete(id); await refreshFiles(j.file); if (window.loadRunsFile) window.loadRunsFile(j.file); }
      } catch (e) { el.innerHTML = `<span style="color:#f87171">lost contact with the server</span>`; jobs.delete(id); }
    }
    setTimeout(poll, 2000);
  }
  poll();

  panel.querySelector("#rp-start").onclick = async () => {
    const mayors = [...panel.querySelectorAll('input[type=checkbox]:not([name])')].filter(c => c.checked).map(c => c.value);
    const seeds = [...panel.querySelectorAll('input[name=seed]')].filter(c => c.checked).map(c => +c.value);
    const terms = +panel.querySelector("#rp-terms").value, label = panel.querySelector("#rp-label").value;
    const msg = panel.querySelector("#rp-msg");
    if (!mayors.length || !seeds.length) { msg.textContent = "pick at least one mayor and one city"; return; }
    msg.textContent = "starting…";
    try {
      const r = await fetch(`${API}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mayors, seeds, terms, hard_starts: true, label }) });
      const j = await r.json(); if (j.error) throw new Error(j.error);
      const el = document.createElement("div"); el.className = "rp-job"; el.textContent = "queued…"; panel.querySelector("#rp-progress").prepend(el); jobs.set(j.id, el);
      msg.textContent = `running ${mayors.length * seeds.length} mayor×city job(s), ${terms} term(s) each`;
    } catch (e) { msg.textContent = `could not start: ${e.message}. Is ask_server.py running?`; }
  };
  refreshFiles("runs.jsonl");
})();
