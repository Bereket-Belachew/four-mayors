// Hero panel: the mayor as a character. A small 3D viewport with the mayor's Kenney figure
// (idle animation, slow auto-rotate, drag to spin), a name plate, and "traits" that are true:
// the loop design and this term's behaviour rendered as skill bars.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const CHAR = "assets/kenney/kenney_blocky-characters/Models/GLB format/";
const FIGURE = { caesar: "character-a", bureaucrat: "character-h", reformer: "character-e", populist: "character-m", reformer_shuffled: "character-e" };
const TITLES = { caesar: "Caesar · the Decider", bureaucrat: "The Bureaucrat · the Consulter", reformer: "The Reformer · the Learner", populist: "The Populist · the Beloved", reformer_shuffled: "The Reformer · shuffled control" };
const EPITHET = { caesar: "Decides alone and fast. Consults no one. Carries nothing between terms.", bureaucrat: "Consults everyone, every year. Keeps every record. Checks none against outcomes.", reformer: "Writes falsifiable lessons. Reviews them next term. Drops the ones that fail.", populist: "The Reformer's method, judged by applause. Lessons live or die by approval.", reformer_shuffled: "The Reformer's memory with the rules shuffled: a token-matched control." };

let renderer, scene, camera, mixer, figure, clock, host, dragging = false, lastX = 0, spin = 0, autoSpin = true, loaded = new Map(), visible = true, acc = 0;
const loader = new GLTFLoader();

export function initHero(container) {
  host = document.createElement("div"); host.id = "hero";
  host.innerHTML = `<div class="hero-view"><canvas></canvas><div class="hero-plate"><div class="hero-name"></div><div class="hero-epithet"></div></div></div><div class="hero-traits"></div>`;
  container.prepend(host);
  const st = document.createElement("style");
  st.textContent = `
    #hero { display:flex; flex-direction:column; gap:8px; }
    .hero-view { position:relative; height:250px; border-radius:12px; overflow:hidden; background: radial-gradient(ellipse at 50% 30%, #2a3142 0%, #0f1115 75%); border:1px solid #2a2f3a; cursor:grab; }
    .hero-view canvas { width:100%; height:100%; display:block; }
    .hero-plate { position:absolute; left:0; right:0; bottom:0; padding:10px 12px; background:linear-gradient(to top, rgba(15,17,21,.95), rgba(15,17,21,0)); pointer-events:none; }
    .hero-name { font-weight:700; font-size:15px; letter-spacing:.3px; } .hero-epithet { font-size:11px; color:#9aa0aa; line-height:1.35; }
    .hero-traits { display:grid; gap:5px; font-size:11px; color:#9aa0aa; }
    .trait { display:grid; grid-template-columns:70px 1fr 56px; gap:6px; align-items:center; }
    .trait .bar { height:7px; background:#0b0d12; border-radius:4px; overflow:hidden; } .trait .bar i { display:block; height:100%; background:#60a5fa; transition:width .6s; }
    .trait.memory .bar i { background:#fbbf24; } .trait.learn .bar i { background:#4ade80; } .trait.borrow .bar i { background:#f87171; } .trait.listen .bar i { background:#c4b5fd; }
    .trait .v { text-align:right; color:#e8e8ea; font-variant-numeric:tabular-nums; }
  `;
  document.head.appendChild(st);
  const canvas = host.querySelector("canvas");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
  new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(canvas);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50); camera.position.set(0, 1.5, 4.9); camera.lookAt(0, 1.0, 0);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.1));
  const key = new THREE.DirectionalLight(0xfff1dd, 1.6); key.position.set(2, 4, 3); scene.add(key);
  const rim = new THREE.DirectionalLight(0x60a5fa, 0.8); rim.position.set(-3, 2, -2); scene.add(rim);
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 0.06, 40), new THREE.MeshStandardMaterial({ color: 0x1f2937, metalness: 0.2, roughness: 0.6 })); disc.position.y = -0.03; scene.add(disc);
  const view = host.querySelector(".hero-view");
  view.addEventListener("pointerdown", e => { dragging = true; autoSpin = false; lastX = e.clientX; view.style.cursor = "grabbing"; });
  addEventListener("pointerup", () => { dragging = false; view.style.cursor = "grab"; });
  view.addEventListener("pointermove", e => { if (dragging) { spin += (e.clientX - lastX) * 0.012; lastX = e.clientX; } });
  view.addEventListener("dblclick", () => autoSpin = true);
  clock = new THREE.Clock();
  new ResizeObserver(() => { const w = view.clientWidth, h = view.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }).observe(view);
  animate();
}

function load(url) {
  if (!loaded.has(url)) loaded.set(url, new Promise((res, rej) => loader.load(url, g => res(g), undefined, rej)));
  return loaded.get(url);
}

export async function setHero(ep) {
  if (!host || !ep) return;
  const m = ep.mayor;
  host.querySelector(".hero-name").textContent = TITLES[m] || m;
  host.querySelector(".hero-epithet").textContent = EPITHET[m] || "";
  try {
    const g = await load(CHAR + (FIGURE[m] || "character-a") + ".glb");
    if (figure) scene.remove(figure);
    figure = g.scene.clone(true);
    const box = new THREE.Box3().setFromObject(figure); const size = box.getSize(new THREE.Vector3());
    const s = 1.9 / Math.max(size.y, 0.01); figure.scale.setScalar(s);
    const box2 = new THREE.Box3().setFromObject(figure); figure.position.y = -box2.min.y;
    scene.add(figure);
    mixer = new THREE.AnimationMixer(figure);
    const idle = g.animations.find(a => a.name === "idle") || g.animations[0];
    if (idle) mixer.clipAction(idle).play();
    // the mayor's mood in the body: unhappy city → arms crossed (emote-no) now and then
  } catch (e) { console.warn("hero load failed", e); }
  traits(ep);
}

function traits(ep) {
  const mem = ep.memory_before || {}, diff = ep.memory_diff || {}, tools = ep.tool_use || {};
  const total = Object.values(tools).reduce((a, b) => a + b, 0) || 1;
  const consults = Object.entries(tools).filter(([k]) => /^consult|^hold_/.test(k)).reduce((a, [, v]) => a + v, 0);
  const reads = tools.read_last_report || 0;
  const loans = tools.borrow || 0;
  const memoryScore = { none: 0, opinion_log: 0.35, lessons: 1, lessons_populist: 0.85 }[mem.policy] ?? 0;
  const checked = diff.checked || [], held = checked.filter(c => c.verdict === "held").length, failed = checked.filter(c => c.verdict === "failed").length;
  const learn = mem.policy === "none" ? 0 : mem.policy === "opinion_log" ? 0.15 : Math.min(1, 0.4 + 0.15 * held + 0.2 * failed);
  const listen = mem.policy === "lessons_populist" ? 1 : consults ? Math.min(1, 0.25 + consults / total * 2) : 0;
  const rows = [
    ["memory", "Memory", memoryScore, { none: "none", opinion_log: "raw log", lessons: "lessons", lessons_populist: "lessons" }[mem.policy] || "—"],
    ["learn", "Learns", learn, mem.policy === "none" ? "never" : mem.policy === "opinion_log" ? "files" : `${held} held · ${failed} failed`],
    ["consult", "Consults", Math.min(1, consults / 20), `${consults} calls`],
    ["listen", "Listens", listen, mem.policy === "lessons_populist" ? "to applause" : consults ? "to advisors" : "to no one"],
    ["borrow", "Borrows", Math.min(1, loans / 8), `${loans} loans`],
    ["reads", "Reviews", Math.min(1, reads / 10), `${reads} reports`],
  ];
  host.querySelector(".hero-traits").innerHTML = rows.map(([cls, label, v, txt]) => `<div class="trait ${cls}"><span>${label}</span><span class="bar"><i style="width:${Math.round(v * 100)}%"></i></span><span class="v">${txt}</span></div>`).join("");
}

function animate() {
  const dt = clock.getDelta();
  acc += dt;
  if (visible && !document.hidden && acc >= 1 / 30) {
    if (mixer) mixer.update(acc);
    if (figure) { if (autoSpin) spin += acc * 0.5; figure.rotation.y = spin; }
    renderer.render(scene, camera);
    acc = 0;
  }
  requestAnimationFrame(animate);
}
