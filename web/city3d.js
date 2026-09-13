// 3D city view. three.js + Kenney City Kits (CC0). Same lot function as the 2D pages.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Cinema, planRecaps, openingRecap } from "./cinema.js?v=1789276410";
import { initCallouts, planCallouts, showCallout, renderCallouts, clearCallouts, updateStage, setAudio, audioEnabled, playSfx } from "./callouts.js?v=1789276410";
import { initHero, setHero } from "./hero.js?v=1789276410";

// ---------- data / controls (mirrors iso.js) ----------
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
  file = file || "runs.jsonl";
  try { const r = await fetch(`../runs/${file}?t=${Date.now()}`); if (r.ok) { window.currentRunFile = file; parse(await r.text()); const rf = document.getElementById('runFile'); if (rf && [...rf.options].some(o => o.value === file)) rf.value = file; } } catch (e) {}
}
function parse(text) {
  timelines.clear();
  episodes = dedupe(text.split("\n").filter(Boolean).map(l => JSON.parse(l)));
  fill("seed", [...new Set(episodes.map(e => e.seed))].sort((a, b) => a - b));
  fill("term", [...new Set(episodes.map(e => e.term))].sort((a, b) => a - b));
  select();
}
function fill(id, xs) { $(id).innerHTML = xs.map(x => `<option>${x}</option>`).join(""); }
function select(keepMayor) {
  const seed = +$("seed").value, term = +$("term").value;
  view = episodes.filter(e => e.seed === seed && e.term === term).sort((a, b) => ORDER.indexOf(a.mayor) - ORDER.indexOf(b.mayor));
  ep = (keepMayor && view.find(e => e.mayor === keepMayor)) || view[0] || null;
  $("tabs").innerHTML = view.map(e => `<div class="tab ${e === ep ? "sel" : ""}" data-m="${e.mayor}">${NAMES[e.mayor] || e.mayor}<span class="sc">${e.scoreboard?.total ?? ""}</span></div>`).join("");
  $("tabs").querySelectorAll(".tab").forEach(t => t.onclick = () => { ep = view.find(e => e.mayor === t.dataset.m); $("tabs").querySelectorAll(".tab").forEach(x => x.classList.toggle("sel", x.dataset.m === t.dataset.m)); recaps = ep ? planRecaps(ep) : []; year = 0; $("scrub").max = ep ? ep.years : 1; rebuild(true); render(); });
  year = 0; $("scrub").max = ep ? ep.years : 1;
  recaps = ep ? planRecaps(ep) : [];
  rebuild(true); render();
}
function stateAt(e, y) { if (y === 0) return e.history[0]?.state_before ?? e.final_state; return e.history[Math.min(y, e.history.length) - 1].state; }

// ---------- lots: identical to index.html tilesFor ----------
const N = 12;
function tilesFor(s) {
  const hu = s.housing, tier = s.economy_tier;
  const houses = Math.min(60, Math.round(hu / 40)), factories = Math.min(20, s.factories), parks = Math.min(20, s.parks), civic = Math.min(12, Math.round(s.services / 12));
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
  return { kinds, tier, pollution: s.pollution, population: s.population };
}
// The picture has memory. tilesFor() says what the numbers *want* on each lot; evolveKinds()
// lets residential lots move one rung a year (shack ↔ house ↔ tower, shuttered as a rung below
// house), at most LOT_STEPS_PER_YEAR lots per year in a fixed order. Non-residential lots follow
// the counts immediately. Returns the new kinds plus the transitions, so a tower emptying out is
// a real event with a spot, not a citywide flip.
const RES = ["shack", "shuttered", "house", "tower"];
const LOT_STEPS_PER_YEAR = 3;
function evolveKinds(prev, target) {
  if (!prev) return { kinds: target.slice(), transitions: [] };
  const kinds = target.slice(), transitions = [];
  let budget = LOT_STEPS_PER_YEAR;
  // fixed visiting order (same permutation the lots use), so the same trajectory draws the same city
  const order = []; for (let k = 0; k < N * N; k++) order.push((k * 37) % (N * N));
  for (const i of order) {
    const a = prev[i], b = target[i];
    if (a === b) continue;
    const ra = RES.indexOf(a), rb = RES.indexOf(b);
    if (ra >= 0 && rb >= 0) {
      if (budget <= 0) { kinds[i] = a; continue; }            // no budget left: stay as you were
      const step = ra < rb ? 1 : -1; kinds[i] = RES[ra + step]; budget--;
      transitions.push({ i, from: a, to: kinds[i], dir: step > 0 ? "up" : "down" });
    } else if (ra >= 0 && rb < 0) {
      transitions.push({ i, from: a, to: b, dir: "replaced" });  // a home became a factory/park/etc: follows the counts
    } else if (ra < 0 && rb >= 0) {
      kinds[i] = RES[Math.min(rb, 2)];                            // new residential lot starts no higher than a house
      transitions.push({ i, from: a, to: kinds[i], dir: "built" });
    }
  }
  return { kinds, transitions };
}
window.lastTransitions = [];
// One timeline per episode: kinds[y] for y = 0..years, so play and the scrubber show the same city.
const timelines = new Map();
function kindsTimeline(e) {
  if (timelines.has(e)) return timelines.get(e);
  let seed = null;
  if (e.inherited) { const prev = episodes.find(p => p.mayor === e.mayor && p.seed === e.seed && p.term === e.term - 1); if (prev) seed = kindsTimeline(prev).kinds[prev.years]; }
  const kinds = [], transitions = [];
  const first = tilesFor(stateAt(e, 0)).kinds;
  let cur = seed ? evolveKinds(seed, first).kinds : first;
  kinds.push(cur); transitions.push([]);
  for (let y = 1; y <= e.years; y++) {
    const ev = evolveKinds(cur, tilesFor(stateAt(e, y)).kinds);
    cur = ev.kinds; kinds.push(cur); transitions.push(ev.transitions.map(t => ({ ...t, r: Math.floor(t.i / N), c: t.i % N })));
  }
  const tl = { kinds, transitions }; timelines.set(e, tl); return tl;
}
function hash(i, salt) { let h = (i * 2654435761 + salt * 40503) >>> 0; h ^= h >>> 13; h = (h * 1274126177) >>> 0; return h >>> 0; }
const pick = (arr, i, salt) => arr[hash(i, salt) % arr.length];

// ---------- models ----------
const K = "assets/kenney/";
const KIT = {
  sub: K + "kenney_city-kit-suburban_20/Models/GLB format/",
  com: K + "kenney_city-kit-commercial_2.1/Models/GLB format/",
  ind: K + "kenney_city-kit-industrial_2.0/Models/GLB format/",
  road: K + "kenney_city-kit-roads/Models/GLB format/",
  car: K + "kenney_car-kit/Models/GLB format/",
};
const MODELS = {
  house: "abcdefghijklmnopqrstu".split("").map(x => KIT.sub + `building-type-${x}.glb`),
  shop: "abcdefghijklmn".split("").map(x => KIT.com + `building-${x}.glb`),
  tower: "abcde".split("").map(x => KIT.com + `building-skyscraper-${x}.glb`),
  shuttered: "abcdefgh".split("").map(x => KIT.com + `low-detail-building-${x}.glb`),
  factory: "abcdefghijklmnopqrst".split("").map(x => KIT.ind + `building-${x}.glb`),
  chimney: ["chimney-small", "chimney-medium", "chimney-large", "chimney-basic"].map(x => KIT.ind + x + ".glb"),
  civic: [KIT.com + "building-n.glb", KIT.com + "building-m.glb", KIT.ind + "water-tower.glb"],
  tree: [KIT.sub + "tree-large.glb", KIT.sub + "tree-small.glb"],
  car: ["sedan", "suv", "taxi", "van", "hatchback-sports", "delivery", "truck", "sedan-sports"].map(x => KIT.car + x + ".glb"),
  road: { straight: KIT.road + "road-straight.glb", bend: KIT.road + "road-bend.glb", t: KIT.road + "road-intersection.glb", cross: KIT.road + "road-crossroad.glb", end: KIT.road + "road-end.glb" },
  light: KIT.road + "light-square.glb",
  barrier: KIT.road + "construction-barrier.glb",
  hall: KIT.com + "building-skyscraper-a.glb",
  cone: KIT.road + "construction-cone.glb",
  dumpster: KIT.road + "dumpster.glb",
  container: ["a", "b", "c"].map(x => KIT.ind + `shipping-container-${x}.glb`),
  billboard: KIT.road + "sign-highway-wide.glb",
  person: "abcdefghijklmnopqr".split("").map(x => K + `kenney_blocky-characters/Models/GLB format/character-${x}.glb`),
};
const distressGroup = new THREE.Group();
const distressMixers = [];
const loader = new GLTFLoader();
const cache = new Map();
function loadModel(url) {
  if (!cache.has(url)) cache.set(url, new Promise((res, rej) => loader.load(url, g => {
    const root = g.scene; root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    const box = new THREE.Box3().setFromObject(root);
    res({ root, box, size: box.getSize(new THREE.Vector3()), animations: g.animations || [] });
  }, undefined, rej)));
  return cache.get(url);
}
// clone a model so it fits a footprint of `fit` tiles wide, standing on y=0, centred
async function place(url, x, z, { fit = 0.9, rotY = 0, minH = 0, maxH = Infinity, scaleOverride = null } = {}) {
  const m = await loadModel(url);
  const obj = m.root.clone(true);
  const s = scaleOverride ?? Math.min(fit / Math.max(m.size.x, m.size.z, 0.01), maxH / Math.max(m.size.y, 0.01));
  obj.scale.setScalar(s);
  const box = new THREE.Box3().setFromObject(obj);
  const c = box.getCenter(new THREE.Vector3());
  obj.position.set(x - c.x, -box.min.y, z - c.z);
  obj.rotation.y = rotY;
  // rotation around own centre: re-centre after rotate
  const box2 = new THREE.Box3().setFromObject(obj); const c2 = box2.getCenter(new THREE.Vector3());
  obj.position.x += x - c2.x; obj.position.z += z - c2.z;
  return obj;
}

// ---------- scene ----------
const game = $("game");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
game.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87b6d9);
scene.fog = new THREE.Fog(0x87b6d9, 30, 90);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true; orbit.dampingFactor = 0.1; orbit.zoomToCursor = true; orbit.zoomSpeed = 1.15; orbit.maxPolarAngle = Math.PI / 2 - 0.05; orbit.minDistance = 3; orbit.maxDistance = 60;
const CENTER = new THREE.Vector3(N / 2 - 0.5, 0, N / 2 - 0.5);
camera.position.set(CENTER.x + 9, 7.5, CENTER.z + 9); orbit.target.copy(CENTER);
const hemi = new THREE.HemisphereLight(0xffffff, 0x556677, 0.9); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff3e0, 1.6); sun.position.set(20, 30, 10); sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024); sun.shadow.camera.left = -14; sun.shadow.camera.right = 14; sun.shadow.camera.top = 14; sun.shadow.camera.bottom = -14; sun.shadow.camera.far = 80; scene.add(sun);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(N + 6, N + 6), new THREE.MeshStandardMaterial({ color: 0x6e8a4a }));
ground.rotation.x = -Math.PI / 2; ground.position.set(CENTER.x, -0.02, CENTER.z); ground.receiveShadow = true; scene.add(ground);
const grassMat = new THREE.MeshStandardMaterial({ color: 0x7fa650 }), dirtMat = new THREE.MeshStandardMaterial({ color: 0xa08a63 }), lotMat = new THREE.MeshStandardMaterial({ color: 0x9a9a92 });
const cityGroup = new THREE.Group(); scene.add(cityGroup);
const carGroup = new THREE.Group(); scene.add(carGroup);
const smokeGroup = new THREE.Group(); scene.add(smokeGroup);
scene.add(distressGroup);
const smokeTex = (() => { const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d"); const rg = g.createRadialGradient(32, 32, 4, 32, 32, 30); rg.addColorStop(0, "rgba(200,200,200,0.9)"); rg.addColorStop(1, "rgba(200,200,200,0)"); g.fillStyle = rg; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); })();

function resize() { const w = game.clientWidth, h = game.clientHeight; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(game); resize();

function roadFor(kinds, r, c) {
  const road = (rr, cc) => rr >= 0 && cc >= 0 && rr < N && cc < N && kinds[rr * N + cc] === "road";
  const n = road(r - 1, c), s = road(r + 1, c), e = road(r, c + 1), w = road(r, c - 1), cnt = n + s + e + w;
  // Kenney road-straight runs along Z by default; bends/intersections need a rotation
  if (cnt === 4) return [MODELS.road.cross, 0];
  if (cnt === 3) return [MODELS.road.t, !n ? 0 : !e ? Math.PI / 2 : !s ? Math.PI : -Math.PI / 2];
  if (n && s) return [MODELS.road.straight, 0];
  if (e && w) return [MODELS.road.straight, Math.PI / 2];
  if (n && e) return [MODELS.road.bend, 0]; if (e && s) return [MODELS.road.bend, -Math.PI / 2]; if (s && w) return [MODELS.road.bend, Math.PI]; if (w && n) return [MODELS.road.bend, Math.PI / 2];
  return [MODELS.road.end, n ? 0 : e ? Math.PI / 2 : s ? Math.PI : -Math.PI / 2];
}

function textSprite(text, color = "#ffffff", bg = "rgba(120,10,10,0.92)") {
  const c = document.createElement("canvas"); c.width = 512; c.height = 128; const g = c.getContext("2d");
  g.fillStyle = bg; g.fillRect(0, 0, 512, 128); g.fillStyle = color; g.font = "bold 64px ui-monospace, Menlo, monospace"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, 256, 64);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true })); sp.scale.set(2.4, 0.6, 1); return sp;
}
// Every one of the seven numbers owns something you can see when it goes bad.
async function distress(s, sb, kinds) {
  while (distressGroup.children.length) distressGroup.remove(distressGroup.children[0]);
  distressMixers.length = 0;
  const roads = [], empties = [], lots = [];
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) { const k = kinds[r * N + c]; if (k === "road") roads.push([r, c]); else if (k === "empty") empties.push([r, c]); else if (k !== "hall") lots.push([r, c]); }
  const pickN = (arr, n, salt) => arr.filter((_, i) => hash(i, salt) % Math.max(1, Math.round(arr.length / Math.max(n, 1))) === 0).slice(0, n);
  const jobs = [];
  // money: negative treasury / heavy debt -> barriers, cones, a debt billboard at the edge
  const moneyBad = s.treasury < 0 || s.debt > 3000;
  if (moneyBad) {
    const sev = Math.min(1, (Math.max(0, -s.treasury) + Math.max(0, s.debt - 3000)) / 6000);
    for (const [r, c] of pickN(roads, Math.round(3 + sev * 9), 21)) jobs.push(place(hash(r * N + c, 2) % 2 ? MODELS.barrier : MODELS.cone, c + 0.25, r + 0.15, { fit: 0.35 }).then(o => distressGroup.add(o)));
    jobs.push(place(MODELS.billboard, N + 0.6, N / 2, { fit: 1.6, rotY: -Math.PI / 2 }).then(o => { distressGroup.add(o); const t = textSprite(`DEBT ${Math.round(s.debt).toLocaleString()}`); t.scale.set(1.5, 0.38, 1); t.position.set(N + 0.6, 2.05, N / 2); distressGroup.add(t); }));
  }
  // services low -> dumpsters on lot corners
  if (s.services < 30) for (const [r, c] of pickN(lots, Math.round(4 + (30 - s.services) / 4), 22)) jobs.push(place(MODELS.dumpster, c + 0.42, r + 0.42, { fit: 0.22 }).then(o => distressGroup.add(o)));
  // jobless -> shipping-container shanties on empty lots
  if ((s.unemployment || 0) > 0.15) for (const [r, c] of pickN(empties, Math.round(2 + s.unemployment * 12), 23)) jobs.push(place(pick(MODELS.container, r * N + c, 3), c, r, { fit: 0.55 }).then(o => distressGroup.add(o)));
  // unhappy -> a standing protest outside city hall
  if (s.happiness < 45) {
    const n = Math.round(4 + (45 - s.happiness) / 4);
    for (let i = 0; i < n; i++) jobs.push(loadModel(MODELS.person[i % MODELS.person.length]).then(m => {
      const o = m.root.clone(true); o.scale.setScalar(0.42 / Math.max(m.size.y, 0.01));
      const a = (i / n) * Math.PI * 1.2 - Math.PI * 0.1; o.position.set(5 + Math.cos(a) * (0.8 + (i % 2) * 0.25), 0, 5 + 0.7 + Math.sin(a) * 0.5); o.lookAt(5, 0, 5);
      const mx = new THREE.AnimationMixer(o); const clip = m.animations.find(x => x.name === (i % 3 ? "emote-no" : "idle")) || m.animations[0]; mx.clipAction(clip).play(); distressMixers.push(mx);
      distressGroup.add(o);
    }));
  }
  await Promise.all(jobs);
  // pollution -> trees brown, grass yellow. score -> light: golden when thriving, flat when failing.
  const pol = Math.min(1, Math.max(0, (s.pollution - 30) / 60));
  grassMat.color.setHex(0x7fa650).lerp(new THREE.Color(0xa8a05a), pol);
  ground.material.color.setHex(0x6e8a4a).lerp(new THREE.Color(0x8f8a55), pol);
  cityGroup.traverse(o => { if (o.isMesh && o.userData.isTree) { if (!o.userData.baseColor) o.userData.baseColor = o.material.color.clone(); o.material = o.material.clone(); o.material.color.copy(o.userData.baseColor).lerp(new THREE.Color(0x7a5a2a), pol * 0.8); } });
  const score = sb ? sb.total / 60 : 0.6;
  const fiscalBad = sb ? Math.min(1, Math.max(0, (2.5 - sb.fiscal) / 2.5)) : 0, moodBad = sb ? Math.min(1, Math.max(0, (4 - sb.wellbeing) / 4)) : 0;
  const failing = Math.min(1, Math.max((0.5 - score) / 0.3, fiscalBad * 0.9, moodBad, moneyBad ? 0.5 : 0, 0));
  const thriving = failing > 0.2 ? 0 : Math.min(1, Math.max(0, (score - 0.45) / 0.35));
  sun.color.setHex(0xfff3e0).lerp(new THREE.Color(0xffc27a), thriving).lerp(new THREE.Color(0xbfc4cc), failing);
  sun.intensity = 1.6 + 0.5 * thriving - 0.9 * failing; hemi.intensity = 0.9 - 0.3 * failing; lastFailing = failing;
}

let buildToken = 0, lotMeta = new Map(), prevKinds = null, currentTier = 3;
let recaps = [];
let cinema = null;
let lastFailing = 0;
async function rebuild(full = false) {
  if (!ep) return;
  const token = ++buildToken;
  const s = stateAt(ep, year);
  const want = tilesFor(s);
  const { tier, pollution, population } = want;
  currentTier = tier;
  const tl = kindsTimeline(ep);
  const yi = Math.min(year, ep.years);
  const kinds = tl.kinds[yi];
  const prev = full ? null : prevKinds;
  window.lastTransitions = tl.transitions[yi] || [];
  // clear
  for (const g of [cityGroup, carGroup, smokeGroup]) { while (g.children.length) { const o = g.children.pop(); o.traverse?.(m => { if (m.isMesh && m.userData.ownGeom) m.geometry.dispose(); }); } }
  lotMeta = new Map();
  const tasks = [];
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    const i = r * N + c, kind = kinds[i], x = c, z = r, changed = prev && prev[i] !== kind;
    tasks.push((async () => {
      let obj = null, label = "";
      const tile = (mat) => { const m = new THREE.Mesh(new THREE.BoxGeometry(1, 0.08, 1), mat); m.position.set(x, 0.04, z); m.receiveShadow = true; m.userData.ownGeom = true; return m; };
      if (kind === "road") { const [url, rot] = roadFor(kinds, r, c); obj = await place(url, x, z, { fit: 1.0, rotY: rot }); }
      else if (kind === "empty") { obj = tile(hash(i, 3) % 3 ? grassMat : dirtMat); }
      else if (kind === "park") { obj = new THREE.Group(); obj.add(tile(grassMat)); for (let k = 0; k < 3; k++) { const t = await place(pick(MODELS.tree, i, k), x + ((hash(i, k) % 60) - 30) / 100, z + ((hash(i, k + 9) % 60) - 30) / 100, { fit: 0.35 + (hash(i, k + 3) % 20) / 100 }); t.traverse(m => { if (m.isMesh) m.userData.isTree = true; }); obj.add(t); } label = "park"; }
      else if (kind === "house") { obj = new THREE.Group(); obj.add(tile(grassMat)); obj.add(await place(pick(MODELS.house, i, 7), x, z, { fit: 0.9, rotY: (hash(i, 1) % 4) * Math.PI / 2 })); label = "a family lives here"; }
      else if (kind === "shack") { obj = new THREE.Group(); obj.add(tile(dirtMat)); obj.add(await place(pick(MODELS.shuttered, i, 7), x, z, { fit: 0.7, maxH: 0.9 })); label = "poor housing"; }
      else if (kind === "shuttered") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.shuttered, i, 8), x, z, { fit: 0.85, maxH: 1.2 })); label = "shuttered"; }
      else if (kind === "tower") { obj = new THREE.Group(); obj.add(tile(lotMat)); const dense = Math.min(1, population / 2500); const h = 1.6 + dense * 3.5 + (hash(i, 5) % 100) / 100 * 1.5; obj.add(await place(pick(MODELS.tower, i, 7), x, z, { fit: 0.85, maxH: h })); label = "apartments"; }
      else if (kind === "factory") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.factory, i, 7), x, z, { fit: 0.95, maxH: 1.8 })); const ch = await place(pick(MODELS.chimney, i, 2), x + 0.3, z - 0.3, { fit: 0.18, maxH: 1.4 }); obj.add(ch); label = "factory";
        const puff = new THREE.Sprite(new THREE.SpriteMaterial({ map: smokeTex, transparent: true, opacity: 0.6, depthWrite: false })); puff.position.set(x + 0.3, 1.5, z - 0.3); puff.scale.setScalar(0.15); puff.userData = { t: hash(i, 4) % 1000 / 1000, x: x + 0.3, z: z - 0.3 }; smokeGroup.add(puff); }
      else if (kind === "civic") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.civic, i, 7), x, z, { fit: 0.9, maxH: 1.8 })); label = "city services"; }
      else if (kind === "hall") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(MODELS.hall, x, z, { fit: 0.95, maxH: 2.2 })); label = "city hall — the mayor"; }
      if (token !== buildToken || !obj) return;
      obj.userData.lot = { r, c, kind, label };
      cityGroup.add(obj);
      lotMeta.set(obj, { r, c, kind, label, x, z });
      if (changed && kind !== "road") { const ring = new THREE.Mesh(new THREE.RingGeometry(0.55, 0.68, 32), new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.9, side: THREE.DoubleSide })); ring.rotation.x = -Math.PI / 2; ring.position.set(x, 0.1, z); ring.userData.fade = 1; cityGroup.add(ring); }
    })());
  }
  // cars on straight road tiles
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    const i = r * N + c; if (kinds[i] !== "road") continue;
    const every = tier === 0 ? 9 : tier === 1 ? 5 : tier === 2 ? 3 : 2;
    if (hash(i, 11) % every !== 0) continue;
    const alongZ = r % 4 !== 3; // roads at r%4==3 run along X; columns c%4==3 run along Z
    tasks.push((async () => {
      const car = await place(pick(MODELS.car, i, 12), c, r, { fit: 0.26, rotY: alongZ ? 0 : Math.PI / 2 });
      if (token !== buildToken) return;
      car.userData.drive = { alongZ, speed: 0.4 + (hash(i, 13) % 50) / 100, lane: alongZ ? 0.2 : -0.2, dir: hash(i, 14) % 2 ? 1 : -1 };
      if (alongZ) car.position.x += 0.22; else car.position.z += 0.22;
      carGroup.add(car);
    })());
  }
  await Promise.all(tasks);
  if (token !== buildToken) return;
  prevKinds = kinds;
  const sby = ep.scoreboard_by_year || [], sbNow = year > 0 ? sby[Math.min(year, sby.length) - 1] : null;
  await distress(s, sbNow, kinds);
  // sky and fog by pollution
  const smog = Math.min(1, pollution / 100);
  const sky = new THREE.Color().lerpColors(new THREE.Color(0x87b6d9), new THREE.Color(0xb59a5a), smog).lerp(new THREE.Color(0x6b7078), lastFailing * 0.8);
  scene.background = sky; scene.fog.color = sky; scene.fog.near = 30 - 22 * smog; scene.fog.far = 90 - 55 * smog;
  hemi.intensity = Math.min(hemi.intensity, 0.9 - 0.35 * smog); sun.intensity = Math.min(sun.intensity, 1.6 - 0.6 * smog);
  $("loading").style.display = "none";
}

// ---------- camera modes ----------
let mode = "orbit";
const keys = {};
let yaw = 0, pitch = -0.05, streetPos = new THREE.Vector3(3, 0.5, 3);
addEventListener("keydown", e => { keys[e.key.toLowerCase()] = true; });
addEventListener("keyup", e => { keys[e.key.toLowerCase()] = false; });
let dragging = false, lastX = 0, lastY = 0;
renderer.domElement.addEventListener("pointerdown", e => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
addEventListener("pointerup", () => dragging = false);
let lastHover = 0, zoomingUntil = 0;
renderer.domElement.addEventListener("wheel", () => { zoomingUntil = performance.now() + 250; $("talk").style.display = "none"; }, { passive: true });
renderer.domElement.addEventListener("pointermove", e => { if (mode === "street" && dragging) { yaw -= (e.clientX - lastX) * 0.004; pitch = Math.max(-1.2, Math.min(0.6, pitch - (e.clientY - lastY) * 0.004)); } lastX = e.clientX; lastY = e.clientY; const now = performance.now(); if (now > zoomingUntil && now - lastHover > 60 && !dragging) { lastHover = now; hoverAt(e); } });
function setMode(m) {
  mode = m; $("camOrbit").classList.toggle("sel", m === "orbit"); $("camStreet").classList.toggle("sel", m === "street");
  orbit.enabled = m === "orbit";
  if (m === "street") { streetPos.set(3, 0.45, -0.8); yaw = 0; pitch = -0.02; }
  else { camera.position.set(CENTER.x + 9, 7.5, CENTER.z + 9); orbit.target.copy(CENTER); }
}
$("camOrbit").onclick = () => setMode("orbit"); $("camStreet").onclick = () => setMode("street");
const sndBtn = document.createElement("button"); sndBtn.id = "sndBtn"; sndBtn.textContent = "🔇"; sndBtn.title = "sound effects (off by default)"; $("togPanel").after(sndBtn);
sndBtn.onclick = () => { setAudio(!audioEnabled()); sndBtn.textContent = audioEnabled() ? "🔊" : "🔇"; if (audioEnabled()) playSfx("chime"); };
const coBtn = document.createElement("button"); coBtn.id = "coBtn"; coBtn.textContent = "🗨 callouts"; coBtn.className = "sel"; coBtn.title = "small windows with a line to the spot, for the smaller moments"; sndBtn.after(coBtn);
window.calloutsOn = true; coBtn.onclick = () => { window.calloutsOn = !window.calloutsOn; coBtn.classList.toggle("sel", window.calloutsOn); };
$("togChamber").onclick = () => { document.body.classList.toggle("no-chamber"); setTimeout(resize, 50); };
$("chMin").onclick = () => { document.body.classList.toggle("no-chamber"); setTimeout(resize, 50); };
document.body.classList.add("no-chamber"); // quiet by default; open it when you want the mayor's thinking
$("togPanel").onclick = () => { document.body.classList.toggle("no-panel"); setTimeout(resize, 50); };


// ---------- hover -> talk button ----------
const ray = new THREE.Raycaster(); const mouse = new THREE.Vector2(); let hovered = null;
let hideT = null;
function hideTalkSoon() { clearTimeout(hideT); hideT = setTimeout(() => { $("talk").style.display = "none"; hovered = null; }, 450); }
function hoverAt(e) {
  if (e.target === $("talk") || $("talk").contains(e.target)) { clearTimeout(hideT); return; }
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hits = ray.intersectObjects(cityGroup.children, true);
  let lot = null;
  for (const h of hits) { let o = h.object; while (o && !o.userData.lot) o = o.parent; if (o && o.userData.lot && !["road", "empty"].includes(o.userData.lot.kind)) { lot = o; break; } if (o) break; }
  if (!lot) { if (hovered) hideTalkSoon(); return; }   // left the building: keep the button up for a moment
  clearTimeout(hideT);
  hovered = lot;
  const meta = lotMeta.get(hovered); if (!meta) return;
  const p = new THREE.Vector3(meta.x, 1.9, meta.z).project(camera);
  const talk = $("talk");
  talk.style.display = "block"; talk.style.left = ((p.x + 1) / 2 * rect.width) + "px"; talk.style.top = ((-p.y + 1) / 2 * rect.height) + "px";
  $("talkLabel").textContent = meta.label;
}
$("talk").addEventListener("pointerenter", () => clearTimeout(hideT));
$("talk").addEventListener("pointerleave", () => hideTalkSoon());
$("talk").onclick = () => { clearTimeout(hideT); stop(); if (ep && window.chroniclerOpen) window.chroniclerOpen(ep, Math.max(1, year)); $("talk").style.display = "none"; hovered = null; };
renderer.domElement.addEventListener("pointerleave", () => hideTalkSoon());

// ---------- animate ----------
const clock = new THREE.Clock();
let frameNo = 0, fpsAcc = 0, fpsN = 0;
function animate() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (cinema) cinema.update(dt);
  updateStage(dt);
  for (const m of distressMixers) m.update(dt);
  if (mode === "orbit" && !(cinema && cinema.playing)) orbit.update();
  else if (mode === "street") {
    const f = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw)), rgt = new THREE.Vector3(f.z, 0, -f.x); const sp = 3 * dt;
    if (keys["w"] || keys["arrowup"]) streetPos.addScaledVector(f, sp); if (keys["s"] || keys["arrowdown"]) streetPos.addScaledVector(f, -sp);
    if (keys["a"] || keys["arrowleft"]) streetPos.addScaledVector(rgt, sp); if (keys["d"] || keys["arrowright"]) streetPos.addScaledVector(rgt, -sp);
    streetPos.x = Math.max(-1, Math.min(N, streetPos.x)); streetPos.z = Math.max(-1, Math.min(N, streetPos.z));
    camera.position.copy(streetPos); camera.lookAt(streetPos.x + Math.sin(yaw) * Math.cos(pitch), streetPos.y + Math.sin(pitch), streetPos.z + Math.cos(yaw) * Math.cos(pitch));
  }
  for (const car of carGroup.children) { const d = car.userData.drive; if (!d) continue; if (d.alongZ) { car.position.z += d.dir * d.speed * dt; if (car.position.z > N + 0.5) car.position.z = -1.5; if (car.position.z < -1.5) car.position.z = N + 0.5; } else { car.position.x += d.dir * d.speed * dt; if (car.position.x > N + 0.5) car.position.x = -1.5; if (car.position.x < -1.5) car.position.x = N + 0.5; } }
  for (const p of smokeGroup.children) { p.userData.t += dt * 0.35; if (p.userData.t > 1) p.userData.t = 0; const t = p.userData.t; p.position.set(p.userData.x + t * 0.35, 1.35 + t * 0.9, p.userData.z + t * 0.1); p.scale.setScalar(0.12 + t * 0.35); p.material.opacity = 0.5 * (1 - t); }
  for (const o of cityGroup.children) if (o.userData.fade !== undefined) { o.userData.fade -= dt * 0.6; o.material.opacity = Math.max(0, o.userData.fade); if (o.userData.fade <= 0) { cityGroup.remove(o); } }
  renderer.render(scene, camera);
  frameNo++;
  renderCallouts(); // every frame: the main render clears the canvas, so skipping frames makes the inset flicker empty
  fpsAcc += dt; fpsN++; if (fpsAcc >= 1) { const el = $("fps"); if (el) el.textContent = `${Math.round(fpsN / fpsAcc)} fps`; fpsAcc = 0; fpsN = 0; }
  requestAnimationFrame(animate);
}
animate();
cinema = new Cinema({ game, scene, camera, orbit, renderer, cityGroup, smokeGroup, get lotMeta() { return lotMeta; }, place, MODELS, N, loadModelFull: loadModel });
initCallouts({ renderer, scene, camera, game, N, loadModelFull: loadModel, place, MODELS });
initHero(document.querySelector("aside"));
window.cinema = cinema; window.recapsFor = () => recaps; window.currentEp = () => ep; window.__dbg = () => ({ ticking, playing, year, orbit: orbit.enabled, transitions: (window.lastTransitions || []).length }); window.showCallout = showCallout;
window.loadRunsFile = async name => { try { const r = await fetch(`../runs/${name}?t=${Date.now()}`); if (r.ok) { window.currentRunFile = name; const keep = ep && ep.mayor; parse(await r.text()); if (keep) select(keep); } } catch (e) {} };

// ---------- council chamber (left): what the mayor saw, heard, decided, and why ----------
const PORTRAIT = { caesar: "character-a", bureaucrat: "character-h", reformer: "character-e", populist: "character-m", reformer_shuffled: "character-e" };
const PERSONA = { caesar: "Decides alone and fast. Consults no one. Carries nothing between terms.", bureaucrat: "Consults everyone, every year. Keeps every record. Checks none of them against outcomes.", reformer: "Writes falsifiable lessons from what actually happened. Reviews them next term. Drops the ones that fail.", populist: "The Reformer's method, but judged by applause: lessons live or die by citizen approval.", reformer_shuffled: "Control: the Reformer's memory with the rules shuffled." };
let feedBuilt = null;
function buildFeed() {
  if (!ep) return;
  $("mayorImg").src = `assets/kenney/kenney_blocky-characters/Previews/${PORTRAIT[ep.mayor] || "character-a"}.png`;
  $("chName").textContent = NAMES[ep.mayor] || ep.mayor; $("chPersona").textContent = PERSONA[ep.mayor] || "";
  const feed = $("feed"); feed.innerHTML = "";
  const mem = ep.memory_before;
  if (mem && mem.policy !== "none" && ep.term > 0) {
    const b = document.createElement("div"); b.className = "bubble memo-bubble";
    b.innerHTML = mem.policy === "opinion_log" ? `<div class="y"><span>carried in</span></div><div class="memo">${mem.opinion_log_entries} records from earlier terms, ${Math.round(mem.opinion_log_chars / 1000)}k characters of advice. None checked.</div>`
      : `<div class="y"><span>carried in</span></div>` + (mem.lessons || []).slice(0, 5).map(l => `<div class="memo">• ${l.rule} <span style="opacity:.6">(${l.confidence})</span></div>`).join("");
    feed.appendChild(b);
  }
  for (const y of ep.history) {
    const s0 = y.state_before, b = document.createElement("div"); b.className = "bubble"; b.dataset.year = y.year;
    const heard = (y.loop_results || []).map(lr => lr.action === "read_last_report" ? "read last year's report" : lr.action === "hold_referendum" ? `referendum on ${lr.args?.proposal}: ${lr.result?.approval_pct}% approve` : `${lr.action.replace("consult_", "")}: “${(lr.result?.advice || "").slice(0, 70)}”`);
    const did = y.actions.length ? y.actions.map(a => `${a.name.replace(/_/g, " ")}${Object.values(a.args).length ? " " + Object.values(a.args).map(v => typeof v === "number" ? Math.round(v * 100) / 100 : v).join(",") : ""}`).join(" · ") : "did nothing";
    b.innerHTML = `<div class="y"><span>year ${y.year}</span><span>pop ${s0.population} · $${s0.treasury} · 😊${s0.happiness}</span></div>
      <div class="saw">saw <b>${s0.jobs}</b> jobs, <b>${Math.round((s0.unemployment || 0) * 100)}%</b> jobless, pollution <b>${s0.pollution}</b>, debt <b>${s0.debt}</b></div>
      ${heard.length ? `<div class="heard">heard: ${heard.join("; ")}</div>` : ""}
      <div class="did">→ ${did}</div>
      ${y.reasoning ? `<div class="why">“${y.reasoning}”</div>` : ""}`;
    feed.appendChild(b);
  }
  feedBuilt = ep;
}
function updateFeed() {
  if (feedBuilt !== ep) buildFeed();
  const feed = $("feed"); let target = null;
  for (const b of feed.querySelectorAll(".bubble[data-year]")) { const y = +b.dataset.year; b.classList.toggle("now", y === year); b.style.display = y <= Math.max(year, 1) ? "" : "none"; if (y === year) target = b; }
  if (target) target.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// ---------- side panel (same as iso.js) ----------
let heroFor = null;
function render() {
  $("year").textContent = `year ${year} / 20`; $("scrub").value = year;
  if (!ep) return;
  if (heroFor !== ep) { heroFor = ep; setHero(ep); }
  updateFeed();
  const s = stateAt(ep, year), rec = year > 0 ? ep.history[Math.min(year, ep.history.length) - 1] : null;
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
let ticking = false;
async function tick() {
  if (ticking) return; ticking = true;
  try {
    const maxY = ep ? ep.years : +$("scrub").max; if (year >= maxY) { stop(); return; }
    year++; await rebuild(false); render();
    const rc = recaps.find(r => r.year === year);
    const autopause = !document.getElementById("ch-autopause") || document.getElementById("ch-autopause").checked;
    if (rc && autopause && cinema) { clearCallouts(); const was = playing; stop(); await cinema.play(rc, ep); if (was) play(); }
    else if (window.calloutsOn !== false && !(cinema && cinema.playing)) {
      const cs = planCallouts(ep, year, lotMeta, N, window.lastTransitions || []);
      if (cs.length) { const wasOrbit = orbit.enabled; orbit.enabled = false; try { await showCallout({ ...cs[0], year }); } catch (e) { console.error("callout failed", e); } finally { orbit.enabled = wasOrbit; } } // the clock waits; the world keeps moving
    }
  } finally { ticking = false; }
}
const opened = new Set();
async function play() {
  if (playing) return stop();
  const autopause = !document.getElementById("ch-autopause") || document.getElementById("ch-autopause").checked;
  if (year === 0 && ep && cinema && autopause && !opened.has(ep)) { opened.add(ep); clearCallouts(); await cinema.play(openingRecap(ep), ep); }
  playing = true; $("play").textContent = "❚❚ pause"; schedule();
}
function schedule() { timer = setTimeout(async () => { await tick(); if (playing) schedule(); }, 10000 / +$("speed").value); }
function stop() { playing = false; clearTimeout(timer); $("play").textContent = "▶ play"; }
window.stop3d = stop;
$("play").onclick = play; $("step").onclick = () => { stop(); tick(); };
$("freeze").onclick = () => { stop(); if (ep && window.chroniclerOpen) window.chroniclerOpen(ep, Math.max(1, year)); };
$("scrub").oninput = e => { stop(); year = +e.target.value; rebuild(true); render(); };
$("seed").onchange = () => select(ep && ep.mayor); $("term").onchange = () => select(ep && ep.mayor);
loadDefault();
