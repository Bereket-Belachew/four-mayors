// Callout windows: the strategy-game inset. The wide view keeps running; a small window pops up
// with a leader line to the spot, showing the close-up. Ambient, several per term, never stops the clock.
// Also a tiny synthesized soundboard (off by default; toggle in the header).
import * as THREE from "three";

const INSET_W = 300, INSET_H = 190, MARGIN = 14, DURATION = 5500;
let R = null; // {renderer, scene, camera, game, N}
let active = [];
let svg = null, box = null, insetCam = null;
const CHAR = "assets/kenney/kenney_blocky-characters/Models/GLB format/";
const CHARS = "abcdefghijklmnopqr".split("").map(x => CHAR + `character-${x}.glb`);
let stageActors = [], stageMixers = [], stageProps = [];
async function actor(url, x, z, anim, faceX, faceZ, scale = 0.42) {
  const m = await R.loadModelFull(url);
  const o = m.root.clone(true); o.scale.setScalar(scale / Math.max(m.size.y, 0.01)); o.position.set(x, 0, z);
  if (faceX !== undefined) o.lookAt(faceX, 0, faceZ);
  const mx = new THREE.AnimationMixer(o); const clip = m.animations.find(a => a.name === anim) || m.animations[0];
  if (clip) { const a = mx.clipAction(clip); a.play(); a.time = Math.random() * clip.duration; }
  o.userData.mixer = mx; o.userData.clips = m.animations; R.scene.add(o); stageActors.push(o); stageMixers.push(mx);
  return o;
}
function clearStage() { for (const a of stageActors) R.scene.remove(a); for (const p of stageProps) R.scene.remove(p); stageActors = []; stageMixers = []; stageProps = []; }
export function updateStage(dt) {
  for (const m of stageMixers) m.update(dt);
  for (const a of stageActors) if (a.userData.path) { const p = a.userData.path; p.t = Math.min(1, p.t + dt / p.dur); const q = p.t < 0.5 ? 2 * p.t * p.t : 1 - Math.pow(-2 * p.t + 2, 2) / 2; a.position.lerpVectors(p.from, p.to, q); if (p.t >= 1 && !p.arrived) { p.arrived = true; if (a.userData.onArrive) a.userData.onArrive(a); } }
  for (const a of stageActors) if (a.userData.orbit) { const o = a.userData.orbit; o.t += dt * o.speed; a.position.set(o.x + Math.cos(o.t) * o.r, 0, o.z + Math.sin(o.t) * o.r); a.lookAt(o.x + Math.cos(o.t + 0.1) * o.r, 0, o.z + Math.sin(o.t + 0.1) * o.r); }
}
// each kind of callout is a small choreographed scene at the spot
async function stagePlay(c) {
  const { x, z } = c.spot; const hall = { x: 5, z: 5 };
  const rnd = i => ((i * 9301 + 49297) % 233280) / 233280;
  switch (c.play) {
    case "crowd": {
      for (let i = 0; i < 10; i++) {
        const sx = x + (rnd(i) - 0.5) * 3.6 + (rnd(i + 3) > 0.5 ? 2.2 : -2.2), sz = z + 1.6 + rnd(i + 7) * 1.4;
        const to = new THREE.Vector3(x - 1.2 + (i % 5) * 0.6 + rnd(i + 11) * 0.15, 0, z + 0.9 + Math.floor(i / 5) * 0.45);
        const a = await actor(CHARS[i % CHARS.length], sx, sz, "sprint", to.x, to.z);
        a.userData.path = { from: a.position.clone(), to, t: 0, dur: 0.9 + rnd(i + 5) * 0.8 };
        a.userData.onArrive = o => { o.lookAt(x, 0, z); playAnim(o, i % 2 ? "emote-no" : "holding-right"); };
      }
      break;
    }
    case "leave": {
      for (let i = 0; i < 5; i++) {
        const a = await actor(CHARS[(i + 4) % CHARS.length], x, z + 0.35, "walk", x + (i - 2) * 0.4, z + 2);
        a.userData.path = { from: a.position.clone(), to: new THREE.Vector3(x + (i - 2) * 0.45, 0, z + 1.4 + (i % 2) * 0.3), t: 0, dur: 1.6 + i * 0.25 };
        a.userData.onArrive = o => playAnim(o, "holding-left");
      }
      const van = await R.place(R.MODELS.car[3], x + 0.9, z + 0.75, { fit: 0.28, rotY: Math.PI / 2 }); R.scene.add(van); stageProps.push(van);
      break;
    }
    case "workers": {
      for (let i = 0; i < 3; i++) {
        const a = await actor(CHARS[(i + 8) % CHARS.length], x + (i - 1) * 0.35, z + 1.6, "walk", x, z);
        a.userData.path = { from: a.position.clone(), to: new THREE.Vector3(x + (i - 1) * 0.3, 0, z + 0.55), t: 0, dur: 1.8 + i * 0.3 };
        a.userData.onArrive = o => playAnim(o, "idle");
      }
      for (let i = 0; i < 3; i++) { const cone = await R.place(R.MODELS.cone, x - 0.5 + i * 0.5, z + 0.7, { fit: 0.12 }); R.scene.add(cone); stageProps.push(cone); }
      break;
    }
    case "picnic": {
      await actor(CHARS[2], x - 0.25, z + 0.25, "sit", x + 1, z + 1);
      await actor(CHARS[6], x + 0.2, z + 0.3, "sit", x - 1, z + 1);
      const kid = await actor(CHARS[11], x + 0.7, z, "sprint", undefined, undefined, 0.3); kid.userData.orbit = { x, z, r: 0.75, t: 0, speed: 1.6 };
      break;
    }
    case "van": {
      const van = await R.place(R.MODELS.car[3], x + 3.0, z + 0.75, { fit: 0.28, rotY: -Math.PI / 2 }); R.scene.add(van); stageProps.push(van);
      van.userData.path = { from: van.position.clone(), to: new THREE.Vector3(x + 0.85, van.position.y, z + 0.75), t: 0, dur: 1.8 }; stageActors.push(van);
      const clerk = await actor(CHARS[14], x + 0.4, z + 0.8, "idle", x + 3, z + 0.8);
      break;
    }
    case "steps": {
      for (let i = 0; i < 4; i++) await actor(CHARS[(i + 12) % CHARS.length], x - 0.6 + i * 0.4, z + 0.7, "sit", x - 0.6 + i * 0.4, z + 3);
      for (let i = 0; i < 2; i++) { const d = await R.place(R.MODELS.dumpster, x + 0.75, z + 0.15 + i * 0.4, { fit: 0.22 }); R.scene.add(d); stageProps.push(d); }
      break;
    }
  }
}
function playAnim(o, name) {
  const mx = o.userData.mixer; if (!mx) return;
  const clips = o.userData.clips; if (!clips) return;
  mx.stopAllAction(); const clip = clips.find(a => a.name === name) || clips[0]; if (clip) mx.clipAction(clip).play();
}

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
  if (down.length) { const t = down[0]; out.push({ kind: "bad", spot: { x: t.c, z: t.r }, play: "leave", title: t.from === "tower" ? "A tower empties out" : "Boarded up", text: `${down.length} building${down.length > 1 ? "s" : ""} downgraded this year. Occupancy ${Math.round(100 * s.population / Math.max(s.housing, 1))}%, happiness ${s.happiness}.`, sfx: "collapse", priority: 50 }); }
  // 2. a factory or park opens
  for (const e of rec.events) {
    if (e.cause_action === "economy" || e.cause_year >= year) continue;
    if (e.variable === "factories") out.push({ kind: "good", spot: lot("factory") || hall, play: "workers", title: "A factory opens", text: `Ordered in year ${e.cause_year}. +${Math.round(150 * e.delta)} jobs, and smoke every year from now on.`, sfx: "thud", priority: 40 });
    else if (e.variable === "parks") out.push({ kind: "good", spot: lot("park") || hall, play: "picnic", title: "A park opens", text: `Ordered in year ${e.cause_year}. It absorbs a share of the air's pollution.`, sfx: "chime", priority: 30 });
  }
  // 3. a loan, taken or refused
  const rec_ = rec.events.find(e => e.cause_action === "recession");
  if (rec_) out.push({ kind: "bad", spot: lot("factory") || hall, play: "workers", title: "Recession", text: `Orders dry up. ${Math.round(-rec_.delta)} jobs gone this year; unemployment ${Math.round(100 * (s.unemployment || 0))}%. Every term gets one. What matters is how fast the city climbs back.`, sfx: "thud", priority: 58 });
  const refused = rec.ignored.find(i => /lenders refuse/.test(i.why));
  if (refused) out.push({ kind: "bad", spot: hall, play: "steps", title: "Lenders refuse", text: refused.why.replace(/^lenders refuse: /, ""), sfx: "thud", priority: 60 });
  const loan = rec.events.find(e => e.cause_action === "borrow" && e.variable === "debt" && e.cause_year === year);
  if (loan) out.push({ kind: "warn", spot: hall, play: "van", title: `Borrowed ${Math.round(loan.delta)}`, text: `Debt is now ${s.debt}. Interest of about ${Math.round(s.debt * 0.08)} a year follows, forever.`, sfx: "cash", priority: 35 });
  // 4. austerity, or services collapsing
  const aust = rec.events.find(e => /austerity/.test(e.note || ""));
  if (aust) out.push({ kind: "bad", spot: lot("civic") || hall, play: "steps", title: "Austerity", text: `The city could not pay its staff. Services ${Math.round(aust.delta)} on top of normal decay. Treasury ${s.treasury}.`, sfx: "thud", priority: 55 });
  else if (s.services < 30 && prev.services >= 30) out.push({ kind: "bad", spot: lot("civic") || hall, play: "steps", title: "Services collapse", text: `Services ${s.services}. Dumpsters on the corners, clinics closing.`, sfx: "thud", priority: 45 });
  // 5. the crowd grows
  const dh = s.happiness - prev.happiness;
  if (s.happiness < 50 && dh <= -3) out.push({ kind: "bad", spot: hall, play: "crowd", title: "The crowd grows", text: `Happiness ${prev.happiness} → ${s.happiness}. More people outside city hall. Tax ${Math.round(s.tax_rate * 100)}%, services ${s.services}, pollution ${s.pollution}.`, sfx: "crowd", priority: 65 });
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
    let x = sx < W / 2 ? MARGIN : W - INSET_W - MARGIN;
    let y = Math.max(MARGIN, Math.min(H - INSET_H - 96, sy - INSET_H / 2));
    // if the window would sit on top of the spot, slide it above or below the spot instead
    if (sx > x - 30 && sx < x + INSET_W + 30 && sy > y - 30 && sy < y + INSET_H + 96) {
      y = sy > H / 2 ? Math.max(MARGIN, sy - INSET_H - 140) : Math.min(H - INSET_H - 96, sy + 70);
    }
    const item = { ...c, el, line, dot, t0: performance.now(), angle: Math.random() * Math.PI * 2, x, y, resolve };
    active.push(item);
    el.style.left = `${x}px`; el.style.top = `${y}px`;
    requestAnimationFrame(() => el.classList.add("in"));
    playSfx(c.sfx);
    if (window.voiceOn && window.speak) window.speak(`${c.title}. ${String(c.text).split(/(?<=\.)\s/)[0]}`);
    if (c.play) stagePlay(c).catch(e => console.warn("callout play failed", e));
    setTimeout(() => { el.classList.remove("in"); setTimeout(() => remove(item), 400); }, c.duration || DURATION);
  });
}
function remove(item) { active = active.filter(a => a !== item); item.el.remove(); item.line.remove(); item.dot.remove(); if (!active.length) clearStage(); item.resolve && item.resolve(); }
export function clearCallouts() { for (const a of active.slice()) remove(a); }
export function calloutsActive() { return active.length > 0; }

// ---------- per-frame: render insets and draw leader lines ----------
export function renderCallouts() {
  if (!R || !active.length) return;
  const { renderer, scene, camera, game } = R;
  const W = game.clientWidth, H = game.clientHeight; // three.js setViewport/setScissor take CSS pixels and apply the pixel ratio themselves
  renderer.autoClear = false;
  active.forEach((a, i) => {
    const t = (performance.now() - a.t0) / 1000;
    const spot = new THREE.Vector3(a.spot.x, 0.5, a.spot.z);
    const ang = a.angle + t * 0.25;
    insetCam.position.set(spot.x + Math.cos(ang) * 2.1, 1.1, spot.z + 0.6 + Math.sin(ang) * 2.1); insetCam.lookAt(spot.x, 0.35, spot.z + 0.6);
    insetCam.aspect = INSET_W / INSET_H; insetCam.updateProjectionMatrix();
    const x = a.x, yTop = a.y;
    const vx = x, vy = H - yTop - INSET_H, vw = INSET_W, vh = INSET_H; // WebGL's origin is bottom-left
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
  renderer.setScissorTest(false); renderer.setViewport(0, 0, W, H);
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
