// Isometric city view. Phaser 3 + Kenney isometric packs (CC0, web/assets/kenney).
// Same state -> same picture: the lot assignment is the same deterministic function as index.html.

// ---------- data / controls (mirrors index.html) ----------
let episodes = [], view = [], ep = null, year = 0, playing = false, timer = null;
const ORDER = ["caesar", "bureaucrat", "reformer", "populist", "reformer_shuffled"];
const NAMES = window.MAYOR_NAMES = { caesar: "Caesar", bureaucrat: "The Bureaucrat", reformer: "The Reformer", populist: "The Populist", reformer_shuffled: "Reformer (shuffled)" };
const $ = id => document.getElementById(id);

function dedupe(eps) {
  const m = new Map(); for (const e of eps) m.set(`${e.mayor}|${e.seed}|${e.term}`, e); // later lines win
  return [...m.values()];
}
async function loadDefault() {
  let file = new URLSearchParams(location.search).get("runs");
  if (!file) { try { const j = await (await fetch("http://localhost:8766/runs")).json(); const first = j.runs.find(r => r.file !== "runs.jsonl" && r.episodes > 0) || j.runs[0]; file = first && first.file; } catch (e) {} }
  file = file || "demo-science.jsonl";
  try { const r = await fetch(`../runs/${file}?t=${Date.now()}`); if (r.ok) { window.currentRunFile = file; parse(await r.text()); const rf = document.getElementById('runFile'); if (rf && [...rf.options].some(o => o.value === file)) rf.value = file; } } catch (e) {}
}
function parse(text) {
  episodes = dedupe(text.split("\n").filter(Boolean).map(l => JSON.parse(l)));
  fill("seed", [...new Set(episodes.map(e => e.seed))].sort((a, b) => a - b));
  fill("term", [...new Set(episodes.map(e => e.term))].sort((a, b) => a - b));
  select();
}
function fill(id, xs) { $(id).innerHTML = xs.map(x => `<option>${x}</option>`).join(""); }
function select(keepMayor) {
  const seed = +$("seed").value, term = +$("term").value;
  view = episodes.filter(e => e.seed === seed && e.term === term).sort((a, b) => ORDER.indexOf(a.mayor) - ORDER.indexOf(b.mayor));
  const want = keepMayor && view.find(e => e.mayor === keepMayor);
  ep = want || view[0] || null;
  $("tabs").innerHTML = view.map(e => `<div class="tab ${e === ep ? "sel" : ""}" data-m="${e.mayor}">${NAMES[e.mayor] || e.mayor}<span class="sc">${e.scoreboard?.total ?? ""}</span></div>`).join("");
  $("tabs").querySelectorAll(".tab").forEach(t => t.onclick = () => { ep = view.find(e => e.mayor === t.dataset.m); $("tabs").querySelectorAll(".tab").forEach(x => x.classList.toggle("sel", x.dataset.m === t.dataset.m)); scene && scene.rebuild(true); render(); });
  year = 0; $("scrub").max = Math.max(...view.map(e => e.years), 1);
  if (scene) scene.rebuild(true);
  render();
}
function stateAt(e, y) { if (y === 0) return e.history[0]?.state_before ?? e.final_state; return e.history[Math.min(y, e.history.length) - 1].state; }

// ---------- lots: identical to index.html tilesFor ----------
const N = 12;
function tilesFor(s) {
  const hu = s.housing, tier = s.economy_tier;
  const houses = Math.min(60, Math.round(hu / 40));
  const factories = Math.min(20, s.factories);
  const parks = Math.min(20, s.parks);
  const civic = Math.min(12, Math.round(s.services / 12));
  const occ = Math.min(1, s.population / Math.max(hu, 1));
  const spots = [];
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) { if (r % 4 === 3 || c % 4 === 3) { spots.push(null); continue; } spots.push([r, c]); }
  const lots = spots.map((p, i) => p ? i : -1).filter(i => i >= 0);
  const perm = lots.map((i, k) => [((k * 37) % lots.length), i]).sort((a, b) => a[0] - b[0]).map(x => x[1]);
  const kinds = new Array(N * N).fill("empty");
  spots.forEach((p, i) => { if (!p) kinds[i] = "road"; });
  const HALL = 5 * N + 5; kinds[HALL] = "hall"; // city hall always stands at the centre lot
  const perm0 = perm.filter(i => i !== HALL); perm.length = 0; perm.push(...perm0);
  let k = 0;
  for (let i = 0; i < houses && k < perm.length; i++, k++) kinds[perm[k]] = occ > 0.9 ? (tier >= 2 ? "tower" : "house") : (occ > 0.6 ? "house" : "shack");
  for (let i = 0; i < factories && k < perm.length; i++, k++) kinds[perm[k]] = "factory";
  for (let i = 0; i < parks && k < perm.length; i++, k++) kinds[perm[k]] = "park";
  for (let i = 0; i < civic && k < perm.length; i++, k++) kinds[perm[k]] = "civic";
  if (tier <= 1) for (let i = 0; i < N * N; i += 7) if (kinds[i] === "house" || kinds[i] === "shack") kinds[i] = "shuttered";
  return { kinds, tier, pollution: s.pollution };
}

// ---------- sprites ----------
const B = i => `b${String(i).padStart(3, "0")}`;
const BUILD = "assets/kenney/kenney_isometric-buildings/PNG/buildingTiles_";
const ROADS = "assets/kenney/kenney_isometric-roads/png/";
// full-lot buildings (with base) chosen from the catalog
const SPR = {
  house:     [B(4), B(12), B(21), B(22), B(14), B(117), B(115)],           // small homes, coloured awnings / brick
  shop:      [B(1), B(9), B(18), B(26), B(28), B(34), B(99), B(108), B(113), B(123)],
  shuttered: [B(19), B(27), B(3)],                                          // blank walls, no windows
  tower_base:[B(93), B(92), B(106), B(122)],                               // stepped two-storey blocks
  tower_story:[B(31), B(50), B(53), B(24)],                                // 99px storeys to stack
  tower_roof:[B(5), B(6), B(13), B(111)],                                  // flat roofs with AC units
  factory_base:[B(3), B(19)],
  factory_roof:[B(104), B(105), B(112), B(88), B(89)],                     // grey barrel / saw-tooth roofs
  civic:     [B(85), B(93)],
};
const ROAD_SCALE = 1.32; // roads pack is 100px wide, buildings are 132
const TW = 132, TH = 66; // diamond footprint

function hash(i, salt) { let h = (i * 2654435761 + salt * 40503) >>> 0; h ^= h >>> 13; h = (h * 1274126177) >>> 0; return h >>> 0; }
function pick(arr, i, salt) { return arr[hash(i, salt) % arr.length]; }

function roadKind(kinds, r, c) {
  const road = (rr, cc) => rr >= 0 && cc >= 0 && rr < N && cc < N && kinds[rr * N + cc] === "road";
  const n = road(r - 1, c), s = road(r + 1, c), e = road(r, c + 1), w = road(r, c - 1);
  const cnt = n + s + e + w;
  if (cnt === 4) return "crossroad";
  if (cnt === 3) return n && s && e ? "crossroadNES" : n && s && w ? "crossroadNSW" : n && e && w ? "crossroadNEW" : "crossroadESW";
  if (n && s) return "roadNS"; if (e && w) return "roadEW";
  if (n && e) return "roadNE"; if (n && w) return "roadNW"; if (s && e) return "roadES"; if (s && w) return "roadSW";
  return "road";
}

// ---------- Phaser scene ----------
let scene = null;
class City extends Phaser.Scene {
  preload() {
    for (let i = 0; i < 129; i++) this.load.image(B(i), `${BUILD}${String(i).padStart(3, "0")}.png`);
    for (const n of ["grass", "road", "roadNS", "roadEW", "roadNE", "roadNW", "roadES", "roadSW", "crossroad", "crossroadNES", "crossroadNSW", "crossroadNEW", "crossroadESW", "treeTall", "treeShort", "treeAltTall", "coniferTall", "lotN", "dirt"]) this.load.image(n, `${ROADS}${n}.png`);
  }
  create() {
    scene = this;
    this.layer = this.add.container(0, 0);
    this.smog = this.add.rectangle(0, 0, 4000, 4000, 0xc8a850, 0).setDepth(10000).setScrollFactor(0);
    this.cameras.main.setBackgroundColor("#3a4a5c");
    this.cameras.main.centerOn(0, N * TH / 2 + 40);
    this.cameras.main.setZoom(0.75);
    // pan + zoom
    this.input.on("pointermove", p => { if (p.isDown && !this._clickedSprite) { this.cameras.main.scrollX -= (p.x - p.prevPosition.x) / this.cameras.main.zoom; this.cameras.main.scrollY -= (p.y - p.prevPosition.y) / this.cameras.main.zoom; } });
    this.input.on("wheel", (p, o, dx, dy) => { const z = Phaser.Math.Clamp(this.cameras.main.zoom * (dy > 0 ? 0.9 : 1.1), 0.35, 2.5); this.cameras.main.setZoom(z); });
    this.prevKinds = null;
    this.sprites = [];
    this.rebuild(true);
    this.scale.on("resize", g => this.cameras.main.setSize(g.width, g.height));
  }
  toScreen(r, c) { return { x: (c - r) * TW / 2, y: (r + c) * TH / 2 }; }
  showChatButton(x, y, label, depth) {
    clearTimeout(this._hideT);
    if (!this.chatBtn) {
      const g = this.add.container(0, 0).setDepth(99999);
      const bg = this.add.rectangle(0, 0, 150, 34, 0x111318, 0.92).setStrokeStyle(1, 0x2563eb).setOrigin(0.5, 1);
      const t = this.add.text(0, -17, "💬 talk", { fontSize: "15px", color: "#e8e8ea" }).setOrigin(0.5, 0.5);
      const sub = this.add.text(0, 6, "", { fontSize: "11px", color: "#9aa0aa" }).setOrigin(0.5, 0);
      g.add([bg, t, sub]); g.bg = bg; g.sub = sub;
      bg.setInteractive({ useHandCursor: true });
      bg.on("pointerover", () => clearTimeout(this._hideT));
      bg.on("pointerout", () => this.hideChatButtonSoon());
      bg.on("pointerdown", () => { this._clickedSprite = true; stop(); if (window.chroniclerOpen && ep) window.chroniclerOpen(ep, Math.max(1, year)); this.chatBtn.setVisible(false); setTimeout(() => this._clickedSprite = false, 50); });
      this.chatBtn = g;
    }
    this.chatBtn.setPosition(x, y).setVisible(true); this.chatBtn.sub.setText(label);
    this.chatBtn.setScale(0.9); this.tweens.add({ targets: this.chatBtn, scale: 1, duration: 120 });
  }
  hideChatButtonSoon() { clearTimeout(this._hideT); this._hideT = setTimeout(() => this.chatBtn && this.chatBtn.setVisible(false), 350); }
  addImg(key, r, c, dy = 0, scale = 1, depthBias = 0) {
    const { x, y } = this.toScreen(r, c);
    const img = this.add.image(x, y + TH / 2 + dy, key).setOrigin(0.5, 1).setScale(scale);
    img.setDepth((r + c) * 10 + depthBias);
    this.layer.add(img);
    return img;
  }
  addLot(kind, i, r, c, changed) {
    const objs = [];
    const salt = 7;
    const ground = () => objs.push(this.addImg("grass", r, c, 0, ROAD_SCALE, 0));
    if (kind === "road") {
      objs.push(this.addImg(roadKind(this.kinds, r, c), r, c, 0, ROAD_SCALE, 0));
    } else if (kind === "empty") {
      objs.push(this.addImg(hash(i, 3) % 3 ? "grass" : "dirt", r, c, 0, ROAD_SCALE, 0));
    } else if (kind === "park") {
      ground();
      const t = ["treeTall", "treeShort", "treeAltTall", "coniferTall"];
      for (let k = 0; k < 3; k++) { const { x, y } = this.toScreen(r, c); const dx = ((hash(i, k) % 60) - 30), dz = ((hash(i, k + 9) % 26) - 13); const im = this.add.image(x + dx, y + TH / 2 - 12 + dz, pick(t, i, k)).setOrigin(0.5, 1).setScale(2.2).setDepth((r + c) * 10 + 2 + k); this.layer.add(im); objs.push(im); }
    } else if (kind === "house") {
      objs.push(this.addImg(pick(SPR.house, i, salt), r, c, 0, 1, 1));
    } else if (kind === "shack") {
      objs.push(this.addImg(pick(SPR.shuttered, i, salt), r, c, 0, 1, 1)); // bare blocks read as poor housing
    } else if (kind === "shuttered") {
      objs.push(this.addImg(pick(SPR.shuttered, i, salt + 1), r, c, 0, 1, 1));
    } else if (kind === "tower") {
      const base = this.addImg(pick(SPR.tower_base, i, salt), r, c, 0, 1, 1); objs.push(base);
      const stories = 1 + (hash(i, 5) % 3);
      for (let k = 0; k < stories; k++) objs.push(this.addImg(pick(SPR.tower_story, i, k), r, c, -78 - k * 44, 1, 2 + k));
      objs.push(this.addImg(pick(SPR.tower_roof, i, salt), r, c, -78 - stories * 44 + 2, 1, 2 + stories));
    } else if (kind === "factory") {
      objs.push(this.addImg(pick(SPR.factory_base, i, salt), r, c, 0, 1, 1));
      objs.push(this.addImg(pick(SPR.factory_roof, i, salt), r, c, -58, 1, 2));
      // smoke puff
      const { x, y } = this.toScreen(r, c);
      const puff = this.add.circle(x + 20, y - 70, 9, 0x9aa0aa, 0.55).setDepth((r + c) * 10 + 3); this.layer.add(puff); objs.push(puff);
      this.tweens.add({ targets: puff, y: y - 110, alpha: 0, scale: 1.8, duration: 2200 + (hash(i, 2) % 900), repeat: -1 });
    } else if (kind === "civic") {
      objs.push(this.addImg(pick(SPR.civic, i, salt), r, c, 0, 1, 1));
    } else if (kind === "hall") {
      objs.push(this.addImg(B(85), r, c, 0, 1, 1));
      objs.push(this.addImg(B(53), r, c, -78, 1, 2));
      objs.push(this.addImg(B(13), r, c, -120, 1, 3));
    }
    if (kind !== "road" && kind !== "empty" && kind !== "park") {
      // hover a building -> a small chat button appears above it; click the button -> freeze & ask
      const top = objs[0]; top.setInteractive({ useHandCursor: false });
      const { x, y } = this.toScreen(r, c);
      const label = { house: "a family lives here", shack: "poor housing", shuttered: "shuttered", tower: "apartments", factory: "factory", civic: "city services", hall: "city hall — the mayor" }[kind] || kind;
      top.on("pointerover", () => this.showChatButton(x, y - (kind === "tower" ? 150 : 90), label, (r + c) * 10 + 50));
      top.on("pointerout", () => this.hideChatButtonSoon());
    }
    if (changed) { // highlight what changed this year
      const { x, y } = this.toScreen(r, c);
      const ring = this.add.ellipse(x, y + TH / 2 - 2, TW * 0.9, TH * 0.9).setStrokeStyle(3, 0xfbbf24, 0.9).setDepth((r + c) * 10 + 0.5); this.layer.add(ring); objs.push(ring);
      this.tweens.add({ targets: ring, alpha: 0, duration: 1800, onComplete: () => ring.destroy() });
    }
    return objs;
  }
  rebuild(full = false) {
    if (!ep) return;
    const s = stateAt(ep, year);
    const { kinds, tier, pollution } = tilesFor(s);
    this.kinds = kinds;
    const prev = full ? null : this.prevKinds;
    this.layer.removeAll(true);
    this.sprites = [];
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const i = r * N + c;
      this.addLot(kinds[i], i, r, c, prev && prev[i] !== kinds[i]);
    }
    // vehicles on roads: horses at tier 0, sparse cars at 1, traffic at 2-3
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const i = r * N + c; if (kinds[i] !== "road") continue;
      const every = tier === 0 ? 7 : tier === 1 ? 5 : 3;
      if (hash(i, 11) % every !== 0) continue;
      const { x, y } = this.toScreen(r, c);
      const t = this.add.text(x - 10, y + TH / 2 - 26, tier === 0 ? "🐎" : "🚗", { fontSize: "22px" }).setDepth((r + c) * 10 + 1); this.layer.add(t);
    }
    // sky: darker and yellower with smog
    const smog = Math.min(1, pollution / 100);
    this.cameras.main.setBackgroundColor(Phaser.Display.Color.GetColor(Math.round(58 + 90 * smog), Math.round(74 + 40 * smog), Math.round(92 - 30 * smog)));
    this.smog.setAlpha(smog * 0.35);
    this.prevKinds = kinds;
  }
}

const game = new Phaser.Game({
  type: Phaser.AUTO, parent: "game", backgroundColor: "#3a4a5c",
  scale: { mode: Phaser.Scale.RESIZE, width: "100%", height: "100%" },
  scene: [City], render: { pixelArt: false, antialias: true },
});

// ---------- side panel ----------
function render() {
  $("year").textContent = `year ${year} / 20`; $("scrub").value = year;
  if (!ep) return;
  const s = stateAt(ep, year);
  const rec = year > 0 ? ep.history[Math.min(year, ep.history.length) - 1] : null;
  $("mayorName").textContent = (NAMES[ep.mayor] || ep.mayor) + (ep.inherited ? " · inherited city" : "");
  $("score").textContent = `score ${ep.scoreboard?.total ?? "–"}`;
  $("decision").textContent = rec ? (rec.actions.length ? rec.actions.map(a => `${a.name}(${Object.values(a.args).map(v => typeof v === "number" ? Math.round(v * 100) / 100 : v).join(",")})`).join(" · ") : "did nothing") + (rec.reasoning ? ` — “${rec.reasoning.slice(0, 160)}”` : "") : `term ${(ep.term ?? 0) + 1} begins · ${ep.scenario || "default"} city`;
  const sby = ep.scoreboard_by_year || [], sb = year > 0 ? sby[Math.min(year, sby.length) - 1] : null;
  const CRIT = [["prosperity", "jobs"], ["housing", "homes"], ["fiscal", "money"], ["environment", "air"], ["wellbeing", "mood"], ["resilience", "resilience"]];
  $("health").innerHTML = CRIT.map(([k, label]) => { const v = sb ? sb[k] : 0, col = v >= 7 ? "var(--good)" : v >= 4 ? "var(--warn)" : "var(--bad)"; return `<div class="hb"><span>${label}</span><span class="ht"><span class="hf" style="width:${Math.round(v * 10)}%;background:${col}"></span></span><span class="hv">${v.toFixed(1)}</span></div>`; }).join("") + (sb ? `<div class="hb total"><span>total</span><span class="ht"><span class="hf" style="width:${Math.round(sb.total / 60 * 100)}%;background:var(--warn)"></span></span><span class="hv">${sb.total.toFixed(1)}</span></div>` : "");
  $("fuse").textContent = rec ? `pending consequences: ${rec.pending_count}` + (year >= ep.years && ep.ended !== "horizon" ? `  ·  ENDED: ${ep.ended.toUpperCase()}` : "") : "";
  $("stats").innerHTML = [["population", s.population], ["jobs", s.jobs], ["treasury", s.treasury], ["debt", s.debt], ["housing", s.housing], ["pollution", s.pollution], ["services", s.services], ["happiness", s.happiness], ["unemployment", Math.round((s.unemployment || 0) * 100) + "%"], ["tax", Math.round(s.tax_rate * 100) + "%"], ["factories", s.factories], ["parks", s.parks]].map(([k, v]) => `<span>${k} <b>${v}</b></span>`).join("");
  const evs = (rec ? rec.events : []).filter(e => e.cause_action !== "economy" || Math.abs(e.delta) > 25).slice(0, 6);
  $("ticker").innerHTML = evs.map(e => `<span class="ev ${e.delta > 0 ? "up" : "down"}">${e.variable} ${e.delta > 0 ? "+" : ""}${Math.round(e.delta)} <span style="opacity:.7">because ${e.cause_action} (y${e.cause_year})${e.note ? ": " + e.note : ""}</span></span>`).join("");
  const before = ep.memory_before?.lessons || [], verdicts = year >= ep.years ? (ep.memory_diff?.checked || []) : [];
  if (ep.memory_before?.policy === "opinion_log") $("lessons").innerHTML = `<span class="l">records carried in: <b>${ep.memory_before.opinion_log_entries}</b> (${Math.round(ep.memory_before.opinion_log_chars / 1000)}k chars, none checked against outcomes)</span>`;
  else if (before.length) $("lessons").innerHTML = before.map(l => { const v = verdicts.find(x => x.rule === l.rule); const cls = v ? (v.verdict === "failed" ? "failed" : v.verdict === "held" ? "held" : "") : ""; return `<span class="l ${cls}">• ${l.rule} <span style="opacity:.6">(${l.confidence})${v && v.deleted ? " — deleted" : v && v.verdict === "failed" ? ` — contradicted, ${v.before}→${v.after}` : ""}</span></span>`; }).join("");
  else $("lessons").innerHTML = `<span class="l" style="opacity:.6">${ep.memory_before?.policy === "none" ? "carries nothing between terms" : "no lessons yet"}</span>`;
}

// ---------- playback ----------
function tick() {
  const maxY = +$("scrub").max; if (year >= maxY) { stop(); return; }
  year++; scene && scene.rebuild(false); render();
  if (window.chroniclerCheck && window.chroniclerCheck([ep], year)) { const was = playing; stop(); window.__resumePlay = () => { if (was) play(); }; }
}
function play() { if (playing) return stop(); playing = true; $("play").textContent = "❚❚ pause"; schedule(); }
function schedule() { timer = setTimeout(() => { tick(); if (playing) schedule(); }, 10000 / +$("speed").value); }
function stop() { playing = false; clearTimeout(timer); $("play").textContent = "▶ play"; }
$("play").onclick = play;
$("step").onclick = () => { stop(); tick(); };
$("freeze").onclick = () => { stop(); if (ep && window.chroniclerOpen) window.chroniclerOpen(ep, Math.max(1, year)); };
$("scrub").oninput = e => { stop(); year = +e.target.value; scene && scene.rebuild(true); render(); };
$("seed").onchange = () => select(ep && ep.mayor);
$("term").onchange = () => select(ep && ep.mayor);
window.currentEp = () => ep;
window.loadRunsFile = async name => { try { const r = await fetch(`../runs/${name}?t=${Date.now()}`); if (r.ok) { window.currentRunFile = name; parse(await r.text()); } } catch (e) {} };
loadDefault();
