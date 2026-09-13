// Callout windows: the strategy-game inset. The wide view keeps running; a small window pops up
// with a leader line to the spot, showing the close-up. Ambient, several per term, never stops the clock.
// Also a tiny synthesized soundboard (off by default; toggle in the header).
import * as THREE from "three";

const INSET_W = 300, INSET_H = 190, MARGIN = 14, DURATION = 4000;
let R = null; // {renderer, scene, camera, game, N}
let active = [];
let svg = null, box = null, insetCam = null;

export function initCallouts(ctx) {
  R = ctx;
  insetCam = new THREE.PerspectiveCamera(38, INSET_W / INSET_H, 0.1, 200);
  box = document.createElement("div"); box.id = "callouts"; R.game.appendChild(box);
  svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.id = "callout-lines"; R.game.appendChild(svg);
  const st = document.createElement("style");
  st.textContent = `
    #callouts { position:absolute; inset:0; pointer-events:none; z-index:4; }
    #callout-lines { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:3; }
    .co { position:absolute; width:${INSET_W}px; pointer-events:auto; }
    .co .frame { width:${INSET_W}px; height:${INSET_H}px; border:2px solid #fbbf24; border-radius:8px; box-shadow:0 10px 30px rgba(0,0,0,.6), 0 0 0 1px #000 inset; background:transparent; }
    .co.bad .frame { border-color:#f87171; } .co.good .frame { border-color:#4ade80; } .co.info .frame { border-color:#60a5fa; }
    .co .cap { margin-top:6px; background:rgba(17,19,24,.94); border:1px solid #2a2f3a; border-radius:8px; padding:6px 9px; color:#e8e8ea; font:12px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
    .co .cap b { display:block; font-size:13px; margin-bottom:2px; } .co.bad .cap b { color:#f87171; } .co.good .cap b { color:#4ade80; } .co.info .cap b { color:#60a5fa; } .co.warn .cap b { color:#fbbf24; }
    .co .cap small { color:#9aa0aa; }
    .co { opacity:0; transform:translateY(-6px); transition:opacity .35s, transform .35s; } .co.in { opacity:1; transform:none; }
    #callout-lines line { stroke:#fbbf24; stroke-width:2; stroke-dasharray:6 4; } #callout-lines circle { fill:#fbbf24; }
    #callout-lines .bad { stroke:#f87171; fill:#f87171; } #callout-lines .good { stroke:#4ade80; fill:#4ade80; } #callout-lines .info { stroke:#60a5fa; fill:#60a5fa; }
  `;
  document.head.appendChild(st);
}

// ---------- planning: which small moments deserve a window this year ----------
const LEVER_WORDS = { build_factory: "a factory", build_park: "a park", build_housing: "new housing", fund_transit: "a transit line", fund_services: "services funding", subsidize_business: "business subsidies", borrow: "a loan" };
export function planCallouts(ep, year, lotMeta, N, transitions = []) {
  const rec = ep.history[year - 1]; if (!rec) return [];
  const prev = year >= 2 ? ep.history[year - 2].state : ep.history[0].state_before, s = rec.state;
  const out = [];
  const lot = kind => { const ls = [...lotMeta.values()].filter(l => l.kind === kind); return ls[ls.length - 1] || null; };
  const hall = lot("hall") || { x: 5, z: 5 };
  // 1. a building comes down: a tower emptied to a house, or a house shuttered
  const down = transitions.filter(t => t.dir === "down");
  if (down.length) { const t = down[0]; out.push({ kind: "bad", spot: { x: t.c, z: t.r }, title: t.from === "tower" ? "A tower empties out" : "Boarded up", text: `${down.length} building${down.length > 1 ? "s" : ""} downgraded this year. Occupancy ${Math.round(100 * s.population / Math.max(s.housing, 1))}%, happiness ${s.happiness}.`, sfx: "collapse", priority: 50 }); }
  // 2. a factory or park opens
  for (const e of rec.events) {
    if (e.cause_action === "economy" || e.cause_year >= year) continue;
    if (e.variable === "factories") out.push({ kind: "good", spot: lot("factory") || hall, title: "A factory opens", text: `Ordered in year ${e.cause_year}. +${Math.round(150 * e.delta)} jobs, and smoke every year from now on.`, sfx: "thud", priority: 40 });
    else if (e.variable === "parks") out.push({ kind: "good", spot: lot("park") || hall, title: "A park opens", text: `Ordered in year ${e.cause_year}. It absorbs a share of the air's pollution.`, sfx: "chime", priority: 30 });
  }
  // 3. a loan, taken or refused
  const refused = rec.ignored.find(i => /lenders refuse/.test(i.why));
  if (refused) out.push({ kind: "bad", spot: hall, title: "Lenders refuse", text: refused.why.replace(/^lenders refuse: /, ""), sfx: "thud", priority: 60 });
  const loan = rec.events.find(e => e.cause_action === "borrow" && e.variable === "debt" && e.cause_year === year);
  if (loan) out.push({ kind: "warn", spot: hall, title: `Borrowed ${Math.round(loan.delta)}`, text: `Debt is now ${s.debt}. Interest of about ${Math.round(s.debt * 0.08)} a year follows, forever.`, sfx: "cash", priority: 35 });
  // 4. austerity, or services collapsing
  const aust = rec.events.find(e => /austerity/.test(e.note || ""));
  if (aust) out.push({ kind: "bad", spot: lot("civic") || hall, title: "Austerity", text: `The city could not pay its staff. Services ${Math.round(aust.delta)} on top of normal decay. Treasury ${s.treasury}.`, sfx: "thud", priority: 55 });
  else if (s.services < 30 && prev.services >= 30) out.push({ kind: "bad", spot: lot("civic") || hall, title: "Services collapse", text: `Services ${s.services}. Dumpsters on the corners, clinics closing.`, sfx: "thud", priority: 45 });
  // 5. the crowd grows
  const dh = s.happiness - prev.happiness;
  if (s.happiness < 50 && dh <= -3) out.push({ kind: "bad", spot: hall, title: "The crowd grows", text: `Happiness ${prev.happiness} → ${s.happiness}. More people outside city hall. Tax ${Math.round(s.tax_rate * 100)}%, services ${s.services}, pollution ${s.pollution}.`, sfx: "crowd", priority: 65 });
  out.sort((a, b) => b.priority - a.priority);
  return out.slice(0, 1); // one at a time, never overwhelm
}

// ---------- showing ----------
export function showCallout(c) {
  if (!R) return Promise.resolve();
  return new Promise(resolve => {
    const el = document.createElement("div"); el.className = `co ${c.kind}`;
    el.innerHTML = `<div class="frame"></div><div class="cap"><b>${c.title}</b>${c.text}<br><small>year ${c.year ?? ""}</small></div>`;
    box.appendChild(el);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line"); line.setAttribute("class", c.kind);
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle"); dot.setAttribute("r", "5"); dot.setAttribute("class", c.kind);
    svg.appendChild(line); svg.appendChild(dot);
    // place the window in free space on the side of the screen nearest the spot, level with it
    const W = R.game.clientWidth, H = R.game.clientHeight;
    const p = new THREE.Vector3(c.spot.x, 0.5, c.spot.z).project(R.camera);
    const sx = (p.x + 1) / 2 * W, sy = (-p.y + 1) / 2 * H;
    const x = sx < W / 2 ? MARGIN : W - INSET_W - MARGIN;
    const y = Math.max(MARGIN, Math.min(H - INSET_H - 96, sy - INSET_H / 2));
    const item = { ...c, el, line, dot, t0: performance.now(), angle: Math.random() * Math.PI * 2, x, y, resolve };
    active.push(item);
    el.style.left = `${x}px`; el.style.top = `${y}px`;
    requestAnimationFrame(() => el.classList.add("in"));
    playSfx(c.sfx);
    setTimeout(() => { el.classList.remove("in"); setTimeout(() => remove(item), 400); }, c.duration || DURATION);
  });
}
function remove(item) { active = active.filter(a => a !== item); item.el.remove(); item.line.remove(); item.dot.remove(); item.resolve && item.resolve(); }
export function clearCallouts() { for (const a of active.slice()) remove(a); }
export function calloutsActive() { return active.length > 0; }

// ---------- per-frame: render insets and draw leader lines ----------
export function renderCallouts() {
  if (!R || !active.length) return;
  const { renderer, scene, camera, game } = R;
  const W = game.clientWidth, H = game.clientHeight, dpr = renderer.getPixelRatio();
  renderer.autoClear = false;
  active.forEach((a, i) => {
    const t = (performance.now() - a.t0) / 1000;
    const spot = new THREE.Vector3(a.spot.x, 0.5, a.spot.z);
    const ang = a.angle + t * 0.25;
    insetCam.position.set(spot.x + Math.cos(ang) * 2.6, 1.7, spot.z + Math.sin(ang) * 2.6); insetCam.lookAt(spot);
    insetCam.aspect = INSET_W / INSET_H; insetCam.updateProjectionMatrix();
    const x = a.x, yTop = a.y;
    const vx = Math.round(x * dpr), vy = Math.round((H - yTop - INSET_H) * dpr), vw = Math.round(INSET_W * dpr), vh = Math.round(INSET_H * dpr);
    renderer.setScissorTest(true); renderer.setScissor(vx, vy, vw, vh); renderer.setViewport(vx, vy, vw, vh);
    renderer.clear(true, true, false);
    renderer.render(scene, insetCam);
    // leader line from the inset's right edge to the spot on the main view
    const p = spot.clone().project(camera);
    const sx = (p.x + 1) / 2 * W, sy = (-p.y + 1) / 2 * H;
    a.line.setAttribute("x1", sx < x ? x : x + INSET_W); a.line.setAttribute("y1", yTop + INSET_H / 2);
    a.line.setAttribute("x2", sx); a.line.setAttribute("y2", sy);
    a.dot.setAttribute("cx", sx); a.dot.setAttribute("cy", sy);
    const visible = p.z < 1 && sx > 0 && sx < W && sy > 0 && sy < H;
    a.line.style.display = a.dot.style.display = visible ? "" : "none";
  });
  renderer.setScissorTest(false); renderer.setViewport(0, 0, Math.round(W * dpr), Math.round(H * dpr));
  renderer.autoClear = true;
}

// ---------- soundboard: synthesized, no assets, off by default ----------
let audioOn = false, actx = null;
export function setAudio(on) { audioOn = on; if (on && !actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (on && actx.state === "suspended") actx.resume(); }
export function audioEnabled() { return audioOn; }
function noise(dur, filterHz, gain) {
  const buf = actx.createBuffer(1, actx.sampleRate * dur, actx.sampleRate); const d = buf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
  const src = actx.createBufferSource(); src.buffer = buf; const f = actx.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = filterHz; const g = actx.createGain(); g.gain.value = gain;
  src.connect(f); f.connect(g); g.connect(actx.destination); src.start();
}
function tone(freq, dur, gain, type = "sine") { const o = actx.createOscillator(); o.type = type; o.frequency.value = freq; const g = actx.createGain(); g.gain.setValueAtTime(gain, actx.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime + dur); o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + dur); }
export function playSfx(kind) {
  if (!audioOn || !actx) return;
  try {
    if (kind === "crowd") { noise(1.6, 900, 0.18); setTimeout(() => noise(1.2, 700, 0.12), 300); }
    else if (kind === "thud") { noise(0.25, 180, 0.5); tone(70, 0.3, 0.3, "triangle"); }
    else if (kind === "cash") { tone(1320, 0.08, 0.12, "square"); setTimeout(() => tone(1760, 0.12, 0.12, "square"), 90); }
    else if (kind === "chime") { tone(880, 0.35, 0.1); setTimeout(() => tone(1108, 0.4, 0.08), 120); }
    else if (kind === "truck") { noise(1.0, 120, 0.35); tone(55, 1.0, 0.15, "sawtooth"); }
    else if (kind === "collapse") { noise(0.9, 140, 0.55); tone(48, 0.9, 0.25, "triangle"); setTimeout(() => noise(0.5, 400, 0.25), 250); }
  } catch (e) {}
}
