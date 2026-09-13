// 3D city view. three.js + Kenney City Kits (CC0). Same lot function as the 2D pages.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Cinema, planRecaps } from "./cinema.js";

// ---------- data / controls (mirrors iso.js) ----------
let episodes = [], view = [], ep = null, year = 0, playing = false, timer = null;
const ORDER = ["caesar", "bureaucrat", "reformer", "populist", "reformer_shuffled"];
const NAMES = window.MAYOR_NAMES = { caesar: "Caesar", bureaucrat: "The Bureaucrat", reformer: "The Reformer", populist: "The Populist", reformer_shuffled: "Reformer (shuffled)" };
const $ = id => document.getElementById(id);
async function loadDefault() { try { const r = await fetch("../runs/runs.jsonl"); if (r.ok) parse(await r.text()); } catch (e) {} }
function parse(text) {
  episodes = text.split("\n").filter(Boolean).map(l => JSON.parse(l));
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
  $("tabs").querySelectorAll(".tab").forEach(t => t.onclick = () => { ep = view.find(e => e.mayor === t.dataset.m); $("tabs").querySelectorAll(".tab").forEach(x => x.classList.toggle("sel", x.dataset.m === t.dataset.m)); recaps = ep ? planRecaps(ep) : []; year = 0; rebuild(true); render(); });
  year = 0; $("scrub").max = Math.max(...view.map(e => e.years), 1);
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
  let k = 0;
  for (let i = 0; i < houses && k < perm.length; i++, k++) kinds[perm[k]] = occ > 0.9 ? (tier >= 2 ? "tower" : "house") : (occ > 0.6 ? "house" : "shack");
  for (let i = 0; i < factories && k < perm.length; i++, k++) kinds[perm[k]] = "factory";
  for (let i = 0; i < parks && k < perm.length; i++, k++) kinds[perm[k]] = "park";
  for (let i = 0; i < civic && k < perm.length; i++, k++) kinds[perm[k]] = "civic";
  if (tier <= 1) for (let i = 0; i < N * N; i += 7) if (kinds[i] === "house" || kinds[i] === "shack") kinds[i] = "shuttered";
  return { kinds, tier, pollution: s.pollution, population: s.population };
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
};
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
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
game.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87b6d9);
scene.fog = new THREE.Fog(0x87b6d9, 30, 90);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true; orbit.maxPolarAngle = Math.PI / 2 - 0.05; orbit.minDistance = 3; orbit.maxDistance = 60;
const CENTER = new THREE.Vector3(N / 2 - 0.5, 0, N / 2 - 0.5);
camera.position.set(CENTER.x + 9, 7.5, CENTER.z + 9); orbit.target.copy(CENTER);
const hemi = new THREE.HemisphereLight(0xffffff, 0x556677, 0.9); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff3e0, 1.6); sun.position.set(20, 30, 10); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); sun.shadow.camera.left = -14; sun.shadow.camera.right = 14; sun.shadow.camera.top = 14; sun.shadow.camera.bottom = -14; sun.shadow.camera.far = 80; scene.add(sun);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(N + 6, N + 6), new THREE.MeshStandardMaterial({ color: 0x6e8a4a }));
ground.rotation.x = -Math.PI / 2; ground.position.set(CENTER.x, -0.02, CENTER.z); ground.receiveShadow = true; scene.add(ground);
const grassMat = new THREE.MeshStandardMaterial({ color: 0x7fa650 }), dirtMat = new THREE.MeshStandardMaterial({ color: 0xa08a63 }), lotMat = new THREE.MeshStandardMaterial({ color: 0x9a9a92 });
const cityGroup = new THREE.Group(); scene.add(cityGroup);
const carGroup = new THREE.Group(); scene.add(carGroup);
const smokeGroup = new THREE.Group(); scene.add(smokeGroup);
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

let buildToken = 0, lotMeta = new Map(), prevKinds = null, currentTier = 3;
let recaps = [];
let cinema = null;
async function rebuild(full = false) {
  if (!ep) return;
  const token = ++buildToken;
  const s = stateAt(ep, year);
  const { kinds, tier, pollution, population } = tilesFor(s);
  currentTier = tier;
  const prev = full ? null : prevKinds;
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
      else if (kind === "park") { obj = new THREE.Group(); obj.add(tile(grassMat)); for (let k = 0; k < 3; k++) { const t = await place(pick(MODELS.tree, i, k), x + ((hash(i, k) % 60) - 30) / 100, z + ((hash(i, k + 9) % 60) - 30) / 100, { fit: 0.35 + (hash(i, k + 3) % 20) / 100 }); obj.add(t); } label = "park"; }
      else if (kind === "house") { obj = new THREE.Group(); obj.add(tile(grassMat)); obj.add(await place(pick(MODELS.house, i, 7), x, z, { fit: 0.9, rotY: (hash(i, 1) % 4) * Math.PI / 2 })); label = "a family lives here"; }
      else if (kind === "shack") { obj = new THREE.Group(); obj.add(tile(dirtMat)); obj.add(await place(pick(MODELS.shuttered, i, 7), x, z, { fit: 0.7, maxH: 0.9 })); label = "poor housing"; }
      else if (kind === "shuttered") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.shuttered, i, 8), x, z, { fit: 0.85, maxH: 1.2 })); label = "shuttered"; }
      else if (kind === "tower") { obj = new THREE.Group(); obj.add(tile(lotMat)); const dense = Math.min(1, population / 2500); const h = 1.6 + dense * 3.5 + (hash(i, 5) % 100) / 100 * 1.5; obj.add(await place(pick(MODELS.tower, i, 7), x, z, { fit: 0.85, maxH: h })); label = "apartments"; }
      else if (kind === "factory") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.factory, i, 7), x, z, { fit: 0.95, maxH: 1.8 })); const ch = await place(pick(MODELS.chimney, i, 2), x + 0.3, z - 0.3, { fit: 0.18, maxH: 1.4 }); obj.add(ch); label = "factory";
        const puff = new THREE.Sprite(new THREE.SpriteMaterial({ map: smokeTex, transparent: true, opacity: 0.6, depthWrite: false })); puff.position.set(x + 0.3, 1.5, z - 0.3); puff.scale.setScalar(0.15); puff.userData = { t: hash(i, 4) % 1000 / 1000, x: x + 0.3, z: z - 0.3 }; smokeGroup.add(puff); }
      else if (kind === "civic") { obj = new THREE.Group(); obj.add(tile(lotMat)); obj.add(await place(pick(MODELS.civic, i, 7), x, z, { fit: 0.9, maxH: 1.8 })); label = "city services"; }
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
  // sky and fog by pollution
  const smog = Math.min(1, pollution / 100);
  const sky = new THREE.Color().lerpColors(new THREE.Color(0x87b6d9), new THREE.Color(0xb59a5a), smog);
  scene.background = sky; scene.fog.color = sky; scene.fog.near = 30 - 22 * smog; scene.fog.far = 90 - 55 * smog;
  hemi.intensity = 0.9 - 0.35 * smog; sun.intensity = 1.6 - 0.6 * smog;
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
renderer.domElement.addEventListener("pointermove", e => { if (mode === "street" && dragging) { yaw -= (e.clientX - lastX) * 0.004; pitch = Math.max(-1.2, Math.min(0.6, pitch - (e.clientY - lastY) * 0.004)); } lastX = e.clientX; lastY = e.clientY; hoverAt(e); });
function setMode(m) {
  mode = m; $("camOrbit").classList.toggle("sel", m === "orbit"); $("camStreet").classList.toggle("sel", m === "street");
  orbit.enabled = m === "orbit";
  if (m === "street") { streetPos.set(3, 0.45, -0.8); yaw = 0; pitch = -0.02; }
  else { camera.position.set(CENTER.x + 9, 7.5, CENTER.z + 9); orbit.target.copy(CENTER); }
}
$("camOrbit").onclick = () => setMode("orbit"); $("camStreet").onclick = () => setMode("street");

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
function animate() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (cinema) cinema.update(dt);
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
  requestAnimationFrame(animate);
}
animate();
cinema = new Cinema({ game, scene, camera, orbit, renderer, cityGroup, smokeGroup, get lotMeta() { return lotMeta; }, place, MODELS, N, loadModelFull: loadModel });
window.cinema = cinema; window.recapsFor = () => recaps; window.currentEp = () => ep;

// ---------- side panel (same as iso.js) ----------
function render() {
  $("year").textContent = `year ${year} / 20`; $("scrub").value = year;
  if (!ep) return;
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
    const maxY = +$("scrub").max; if (year >= maxY) { stop(); return; }
    year++; await rebuild(false); render();
    const rc = recaps.find(r => r.year === year);
    const autopause = !document.getElementById("ch-autopause") || document.getElementById("ch-autopause").checked;
    if (rc && autopause && cinema) { const was = playing; stop(); await cinema.play(rc, ep); if (was) play(); }
  } finally { ticking = false; }
}
function play() { if (playing) return stop(); playing = true; $("play").textContent = "❚❚ pause"; schedule(); }
function schedule() { timer = setTimeout(async () => { await tick(); if (playing) schedule(); }, 10000 / +$("speed").value); }
function stop() { playing = false; clearTimeout(timer); $("play").textContent = "▶ play"; }
window.stop3d = stop;
$("play").onclick = play; $("step").onclick = () => { stop(); tick(); };
$("freeze").onclick = () => { stop(); if (ep && window.chroniclerOpen) window.chroniclerOpen(ep, Math.max(1, year)); };
$("scrub").oninput = e => { stop(); year = +e.target.value; rebuild(true); render(); };
$("seed").onchange = () => select(ep && ep.mayor); $("term").onchange = () => select(ep && ep.mayor);
loadDefault();
