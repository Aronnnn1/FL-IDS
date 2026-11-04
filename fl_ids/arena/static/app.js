"use strict";
// ================================================================ constants
const STATIC = !!window.ARENA_STATIC;           // hosted page: no server, interactive simulator over precomputed real verdicts
const SHORT = { normal: "Normal", idle: "Idle", Backdoor: "Backdoor", DDoS_HTTP: "DDoS HTTP", DDoS_ICMP: "DDoS ICMP", DDoS_TCP: "DDoS TCP",
  DDoS_UDP: "DDoS UDP", Fingerprinting: "Fingerprint", MITM: "MITM", Password: "Password", Port_Scanning: "Port scan",
  Ransomware: "Ransomware", SQL_injection: "SQL inj.", Uploading: "Uploading", Vulnerability_scanner: "Vuln. scan", XSS: "XSS", anomalous: "Anomalous", benign: "Normal" };
const LONG = (s) => (s || "").replace(/_/g, " ");
const C = { idle: "#9aa8bd", send: "#2e75b6", ana: "#e69b00", ok: "#16a34a", bad: "#dc2626", miss: "#7c3aed", warn: "#ea580c" };
const NS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);
const fmt = (n) => Number(n).toLocaleString("en-US");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
const DEFAULT_TOPO = { 1: 3, 2: 3, 3: 3, 4: 3, 5: 3 };
const NET_NOTE = { 9: "model flags about 22% of its own normal traffic (near the 25% rule)", 0: "calibrated on only 224 normal rows" };

let CFG = null, V = null, S = freshState(), mode = "live", nextEv = 0, selected = null, replayTimer = null, benchmark = null, simT0 = 0, simTimers = [];
let hostPos = {}, routes = {}, layoutInfo = null;
const dots = [];

function freshState(topo) { return { hosts: {}, feed: [], narr: "", topo: { ...(topo || DEFAULT_TOPO) }, speed: 1 }; }
function H(id) { return S.hosts[id] || (S.hosts[id] = { id, role: "idle", phase: "idle", packets: 0, total: 0, source: null, verdict: null, mit: null, dropped: 0, ttb: null }); }
const nets = () => Object.keys(S.topo).map(Number).sort((a, b) => a - b);
const activeIds = () => nets().flatMap((k) => Array.from({ length: S.topo[k] }, (_, j) => `c${k}h${j + 1}`));
const busyIds = () => Object.values(S.hosts).filter((h) => ["sending", "analysing"].includes(h.phase)).map((h) => h.id);

// ================================================================ reducer (live events, recordings and the simulator share it)
function apply(ev) {
  const stamp = ev.t.toFixed(1).padStart(5, " ");
  const feed = (html) => S.feed.unshift(`<div><span class="t">${stamp}s</span>${html}</div>`);
  switch (ev.type) {
    case "boot": S.narr = "Network is up: controller, core switch and every client network are ready."; break;
    case "reset": S = freshState(S.topo); S.narr = "Reset. All rules cleared. Give the hosts new roles."; break;
    case "topology": S.topo = Object.fromEntries(Object.entries(ev.nets).map(([k, v]) => [Number(k), v])); break;
    case "speed": S.speed = ev.value; break;
    case "role": { const h = H(ev.host); Object.assign(h, { role: ev.role, phase: ev.role === "idle" ? "idle" : "armed", verdict: null, mit: null, packets: 0, dropped: 0, ttb: null }); break; }
    case "launch": { S.narr = `${ev.host} launched as ${ev.role === "normal" ? "a normal device" : LONG(ev.role)}. Window of ${fmt(CFG.window)} packets is being collected.`; const h = H(ev.host);
      Object.assign(h, { role: ev.role, phase: "sending", packets: 0, total: 0, verdict: null, mit: null, dropped: 0, ttb: null });
      feed(ev.role === "normal" ? `<b>${ev.host}</b> starts as a <b>normal</b> device (scored on real normal rows from the dataset).`
        : `<b>${ev.host}</b> starts a real <b>${LONG(ev.role)}</b> attack: replaying captured packets through its switch.`); break; }
    case "progress": { const h = H(ev.host); Object.assign(h, { packets: ev.packets, total: ev.total, source: ev.source }); break; }
    case "analysing": { const h = H(ev.host); h.phase = "analysing"; S.narr = `${ev.host}: window complete. The cascade is judging it now.`; feed(`<b>${ev.host}</b>: window complete, running the cascade.`); break; }
    case "verdict": { const h = H(ev.host); h.verdict = ev;
      S.narr = ev.is_attack ? `${ev.host} judged an attacker: ${LONG(ev.label)} (${pct(ev.confidence)}). Sending the verdict to the controller.` : `${ev.host} judged normal (${pct(ev.share, 1)} of packets flagged). No rule installed.`;
      const stage = ev.stage === "boosting" ? "the classifier (LightGBM)" : "the autoencoder backstop";
      if (ev.is_attack) feed(`<b>${ev.host}</b> judged an <b>attacker: ${LONG(ev.label)}</b> (${pct(ev.confidence)}), ${pct(ev.share, 0)} of ${fmt(ev.packets)} packets flagged by ${stage}. ${ev.truth === "normal" ? '<span class="tag warn">false alarm</span>' : ev.type_ok ? '<span class="tag ok">type correct</span>' : '<span class="tag warn">type differs from truth</span>'}`);
      else feed(`<b>${ev.host}</b> judged <b>normal</b>: only ${pct(ev.share, 1)} of ${fmt(ev.packets)} packets flagged. ${ev.truth === "normal" ? '<span class="tag ok">correct</span>' : '<span class="tag bad">missed attack</span>'}`);
      break; }
    case "mitigation": { const h = H(ev.host); h.mit = ev; h.ttb = ev.time_to_action_s; h.phase = "mitigated";
      if (ev.action === "block") { feed(`Controller installed a <b>DROP rule</b> for <b>${ev.host}</b> on its switch (${ev.time_to_action_s}s after launch).`); S.narr = `${ev.host} blocked ${ev.time_to_action_s}s after it started.`; }
      else if (ev.action === "rate_limit") feed(`Controller <b>rate-limited</b> ${ev.host} (confidence below the block threshold).`);
      else if (h.verdict && h.verdict.is_attack) feed(`<b>${ev.host}</b> was flagged but <b>not blocked</b>: confidence ${pct(h.verdict.confidence)} is below the 50% threshold for any rule.`);
      break; }
    case "dropped": { H(ev.host).dropped = ev.packets; break; }
    case "host_done": { const h = H(ev.host); if (h.phase !== "idle") h.phase = "done"; break; }
    case "run_done": feed("<b>Run finished.</b> See the Results tab for the scoreboard."); S.narr = "Run finished. Results are in the Results tab."; break;
    case "error": feed(`<span class="tag bad">error</span> ${ev.host || ""} ${ev.message}`); break;
  }
}

// ================================================================ derived state
function hostStatus(h) {
  const v = h.verdict, m = h.mit;
  if (v && m) {
    const attackTruth = v.truth !== "normal";
    if (m.action === "block") return attackTruth ? { t: "BLOCKED", c: C.bad } : { t: "FALSE ALARM", c: C.warn };
    if (m.action === "rate_limit") return { t: "RATE-LIMITED", c: C.warn };
    return attackTruth ? { t: v.is_attack ? "NOT BLOCKED" : "MISSED", c: C.miss } : { t: "ALLOWED ✓", c: C.ok };
  }
  if (h.phase === "analysing") return { t: "ANALYSING", c: C.ana };
  if (h.phase === "sending") return { t: h.source === "dataset" ? "SCORING" : "SENDING", c: C.send };
  if (h.phase === "armed") return { t: "READY", c: C.send };
  return { t: "", c: C.idle };
}
const hostColor = (h) => (h.phase === "idle" ? C.idle : hostStatus(h).c);
function score() {
  const act = new Set(activeIds());
  const vs = Object.values(S.hosts).filter((h) => h.verdict && act.has(h.id));
  const atk = vs.filter((h) => h.verdict.truth !== "normal"), nor = vs.filter((h) => h.verdict.truth === "normal");
  const blocked = vs.filter((h) => h.mit && h.mit.action === "block");
  return {
    tested: vs.length, attacks: atk.length, atkDetected: atk.filter((h) => h.verdict.is_attack).length,
    atkBlocked: atk.filter((h) => h.mit && h.mit.action === "block").length, typeOk: atk.filter((h) => h.verdict.type_ok).length,
    normals: nor.length, falseBlocks: nor.filter((h) => h.mit && h.mit.action === "block").length,
    ttb: blocked.length ? blocked.reduce((a, h) => a + h.mit.time_to_action_s, 0) / blocked.length : null,
    dropped: vs.reduce((a, h) => a + (h.dropped || 0), 0),
  };
}

// ================================================================ map layout and drawing
function el(tag, attrs = {}, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function text(parent, x, y, s, attrs = {}) { const t = el("text", { x, y, "text-anchor": "middle", ...attrs }, parent); t.textContent = s; return t; }

function computeLayout() {
  const ns = nets(), maxH = Math.max(...ns.map((k) => S.topo[k]));
  const boxW = Math.max(230, maxH * 74 + 36), gap = 16;
  const single = ns.length * (boxW + gap) <= 1560;
  const perRow = single ? ns.length : 4, rows = Math.ceil(ns.length / perRow);
  const W = perRow * (boxW + gap), coreX = W / 2, coreY = 140, ctrlY = 40, swY0 = 252, rowH = 352, boxH = 262;
  const info = { ns, boxW, gap, perRow, rows, W, coreX, coreY, ctrlY, boxH, H: swY0 + (rows - 1) * rowH + boxH + 52, nets: {} };
  hostPos = {}; routes = {};
  ns.forEach((k, i) => {
    const r = Math.floor(i / perRow), c = i % perRow, inRow = Math.min(perRow, ns.length - r * perRow);
    const cx = (W - inRow * (boxW + gap)) / 2 + gap / 2 + boxW / 2 + c * (boxW + gap), swY = swY0 + r * rowH;
    info.nets[k] = { cx, swY, r };
    const busY = swY - 52;
    const route = r === 0 ? [[cx, swY + 18], [coreX, coreY + 20]] : [[cx, swY + 18], [cx, busY], [coreX, busY], [coreX, coreY + 20]];
    for (let j = 1; j <= S.topo[k]; j++) {
      const id = `c${k}h${j}`, hx = cx + (j - (S.topo[k] + 1) / 2) * 74, hy = swY + 112;
      hostPos[id] = { x: hx, y: hy, sx: cx, sy: swY + 18 };
      routes[id] = [[hx, hy - 26], ...route];
    }
  });
  layoutInfo = info;
  return info;
}

let mapSig = "";
function buildMap() {
  const L = computeLayout(), svg = $("#map");
  svg.setAttribute("viewBox", `0 0 ${L.W} ${L.H}`);
  svg.innerHTML = "";
  const g = el("g", {}, svg);
  el("line", { x1: L.coreX, y1: L.ctrlY + 24, x2: L.coreX, y2: L.coreY - 20, stroke: "#9aa8bd", "stroke-width": 2, "stroke-dasharray": "5 5" }, g);
  text(g, L.coreX + 78, 100, "OpenFlow control", { "font-size": 13, fill: "#5b6b85", "text-anchor": "start" });
  const row1 = Object.values(L.nets).filter((n) => n.r === 1);
  const busY1 = row1.length ? Math.min(...row1.map((n) => n.swY)) - 52 : 0;
  if (row1.length) {
    const xs = row1.map((n) => n.cx);
    el("line", { x1: L.coreX, y1: L.coreY + 20, x2: L.coreX, y2: busY1, stroke: "#b8c4d8", "stroke-width": 3 }, g);
    el("line", { x1: Math.min(...xs), y1: busY1, x2: Math.max(...xs), y2: busY1, stroke: "#b8c4d8", "stroke-width": 3 }, g);
  }
  const c = el("g", {}, g);
  el("rect", { x: L.coreX - 170, y: L.ctrlY - 26, width: 340, height: 52, rx: 12, fill: "#1f3864" }, c);
  text(c, L.coreX, L.ctrlY - 3, "SDN controller + mitigation bridge", { fill: "#fff", "font-size": 16, "font-weight": 700 });
  text(c, L.coreX, L.ctrlY + 15, "installs drop / rate-limit rules", { fill: "#cadcfc", "font-size": 12.5 });
  el("rect", { x: L.coreX - 90, y: L.coreY - 21, width: 180, height: 42, rx: 10, fill: "#e8eefb", stroke: "#2e75b6", "stroke-width": 2 }, g);
  text(g, L.coreX, L.coreY + 5, "Core switch", { "font-size": 15, "font-weight": 700, fill: "#1f3864" });
  L.ns.forEach((k) => {
    const { cx, swY, r } = L.nets[k], n = S.topo[k];
    if (r === 0) el("line", { x1: L.coreX, y1: L.coreY + 21, x2: cx, y2: swY - 18, stroke: "#b8c4d8", "stroke-width": 3 }, g);
    else el("line", { x1: cx, y1: busY1, x2: cx, y2: swY - 18, stroke: "#b8c4d8", "stroke-width": 3 }, g);
    const bx = cx - L.boxW / 2, by = swY + 36;
    el("rect", { x: bx, y: by, width: L.boxW, height: L.boxH, rx: 16, fill: "#f4f7fb", stroke: "#dbe3ef", "stroke-width": 1.5 }, g);
    el("rect", { x: cx - 58, y: swY - 18, width: 116, height: 36, rx: 9, fill: "#e8eefb", stroke: "#2e75b6", "stroke-width": 1.5 }, g);
    text(g, cx, swY + 5, `Switch s${k + 1}`, { "font-size": 14, "font-weight": 600, fill: "#1f3864" });
    for (let j = 1; j <= n; j++) { const p = hostPos[`c${k}h${j}`]; el("line", { x1: p.x, y1: p.y - 26, x2: cx, y2: swY + 18, stroke: "#b8c4d8", "stroke-width": 2, id: `link-c${k}h${j}` }, g); }
    text(g, cx, by + L.boxH - 42, `Client ${k} network · ${n} host${n > 1 ? "s" : ""}`, { "font-size": 16, "font-weight": 700, fill: "#14213d" });
    const note = NET_NOTE[CFG.bundle_clients ? CFG.bundle_clients[k] : -1];
    text(g, cx, by + L.boxH - 24, note ? "⚠ " + note : "own model scaler + threshold", { "font-size": 11.5, fill: note ? "#b45309" : "#5b6b85" });
    const editable = canEdit();
    const btn = (x, label, act, ok) => {
      const b = el("g", { style: `cursor:${ok ? "pointer" : "not-allowed"}`, opacity: ok ? 1 : 0.35 }, g);
      el("rect", { x: x - 24, y: by + L.boxH - 19, width: 48, height: 17, rx: 8.5, fill: "#fff", stroke: "#9aa8bd" }, b);
      text(b, x, by + L.boxH - 6.5, label, { "font-size": 11.5, "font-weight": 700, fill: "#1f3864" });
      if (ok) b.addEventListener("click", (e) => { e.stopPropagation(); topoChange(act, k); });
    };
    btn(bx + 34, "+ host", "add_host", editable && n < (CFG.max_hosts || 5));
    btn(bx + L.boxW - 34, "− host", "remove_host", editable && n > 1);
  });
  el("g", { id: "hostlayer" }, svg);
  el("g", { id: "dotlayer" }, svg);
}

function sigNow() {
  return JSON.stringify([S.topo, selected, canEdit(), activeIds().map((id) => { const h = H(id); return [h.role, h.phase, Math.round((h.packets / (h.total || 1)) * 40), h.verdict && h.verdict.label, h.mit && h.mit.action, Math.floor((h.dropped || 0) / 100)]; })]);
}
function render(force) {
  const sig = sigNow();
  if (!force && sig === mapSig) { $("#narr").textContent = S.narr || defaultNarr(); return; }
  const structSig = JSON.stringify([S.topo, canEdit()]);
  if (force || render.structSig !== structSig) { render.structSig = structSig; buildMap(); }
  mapSig = sig;
  const layer = $("#hostlayer"); layer.innerHTML = "";
  for (const id of activeIds()) {
    const h = H(id), p = hostPos[id], col = hostColor(h), st = hostStatus(h);
    const g = el("g", { class: "host", transform: `translate(${p.x},${p.y})` }, layer);
    g.addEventListener("click", () => { selected = id; activateTab("host"); refreshTabs(true); render(); });
    if (h.phase === "sending") el("circle", { class: "ring", cx: 0, cy: 0, r: 28, stroke: col }, g);
    if (selected === id) el("circle", { cx: 0, cy: 0, r: 33, fill: "none", stroke: "#1f3864", "stroke-width": 2, "stroke-dasharray": "4 4" }, g);
    el("circle", { class: "body", cx: 0, cy: 0, r: 25, fill: h.phase === "idle" ? "#fff" : col, stroke: col, "stroke-width": 3 }, g);
    const mono = h.phase === "idle" ? C.idle : "#fff";
    el("rect", { x: -11, y: -10, width: 22, height: 15, rx: 2.5, fill: "none", stroke: mono, "stroke-width": 2 }, g);
    el("line", { x1: -6, y1: 10, x2: 6, y2: 10, stroke: mono, "stroke-width": 2 }, g);
    if (h.phase === "analysing") el("circle", { class: "spin", cx: 0, cy: 0, r: 31, fill: "none", stroke: C.ana, "stroke-width": 3, "stroke-dasharray": "22 60" }, g);
    if (h.mit && h.mit.action === "block") { el("circle", { cx: 18, cy: -18, r: 10, fill: C.bad, stroke: "#fff", "stroke-width": 2 }, g); text(g, 18, -13.5, "✖", { fill: "#fff", "font-size": 12, "font-weight": 700 }); }
    text(g, 0, 45, id, { "font-size": 14, "font-weight": 700, fill: "#14213d" });
    const label = SHORT[h.role] || h.role, w = Math.max(50, label.length * 6.2 + 12);
    el("rect", { x: -w / 2, y: 52, width: w, height: 19, rx: 9.5, fill: h.role === "idle" ? "#edf1f7" : h.role === "normal" ? "#dcfce7" : "#fee2e2" }, g);
    text(g, 0, 65.5, label, { "font-size": 11.5, "font-weight": 600, fill: h.role === "idle" ? "#7a889e" : h.role === "normal" ? "#166534" : "#991b1b" });
    if (st.t) text(g, 0, 87, st.t, { "font-size": 12, "font-weight": 700, fill: st.c });
    if (h.phase === "sending" && h.total) {
      el("rect", { x: -30, y: 93, width: 60, height: 6, rx: 3, fill: "#e6ecf5" }, g);
      el("rect", { x: -30, y: 93, width: Math.max(1, 60 * Math.min(1, h.packets / h.total)), height: 6, rx: 3, fill: C.send }, g);
    } else if (h.verdict) {
      text(g, 0, 102, h.mit && h.mit.action === "block" && h.dropped ? `dropped ${fmt(h.dropped)}` : `${pct(h.verdict.confidence, 0)} conf.`, { "font-size": 11.5, fill: "#5b6b85" });
    }
    const lk = $(`#link-${id}`);
    if (lk) { const blocked = h.mit && h.mit.action === "block"; lk.setAttribute("stroke", blocked ? C.bad : h.phase === "sending" ? C.send : "#b8c4d8"); lk.setAttribute("stroke-dasharray", blocked ? "6 5" : ""); lk.setAttribute("stroke-width", blocked || h.phase === "sending" ? 3 : 2); }
  }
  $("#narr").textContent = S.narr || defaultNarr();
}
const defaultNarr = () => (STATIC ? "Simulator: give hosts roles (click a host or use Scenario), then Launch. Verdicts are the real cascade outputs; packets are not sent on this page." : "Start the network, give each host a role (click a host), then launch.");

// packet animation (illustrative: dots only show that traffic flows; counts elsewhere are real)
function along(pts, t) {
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1])), tot = seg.reduce((a, b) => a + b, 0);
  let d = t * tot;
  for (let i = 0; i < seg.length; i++) { if (d <= seg[i]) { const q = seg[i] ? d / seg[i] : 0; return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * q, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * q]; } d -= seg[i]; }
  return pts[pts.length - 1];
}
let lastSpawn = 0;
function frame(ts) {
  const layer = $("#dotlayer");
  if (layer) {
    if (ts - lastSpawn > Math.max(60, 140 / Math.max(0.25, S.speed))) {
      lastSpawn = ts;
      for (const id of activeIds()) {
        const h = S.hosts[id]; if (!h) continue;
        if (h.phase === "sending") dots.push({ id, p: 0, c: h.source === "dataset" ? "#16a34a" : "#dc2626" });
        else if (h.mit && h.mit.action === "block" && h.dropped && !["idle", "armed"].includes(h.phase)) dots.push({ id, p: 0, c: "#dc2626", blocked: true });
      }
    }
    layer.innerHTML = "";
    const stepSize = 0.028 * Math.min(3, Math.max(0.5, S.speed));
    for (let i = dots.length - 1; i >= 0; i--) {
      const d = dots[i], r = routes[d.id];
      d.p += d.blocked ? 0.035 : stepSize;
      if (!r || d.p > 1 || (d.blocked && d.p > 0.25)) { dots.splice(i, 1); continue; }
      const [x, y] = along(r, d.p);
      el("circle", { cx: x, cy: y, r: 4.5, fill: d.c, opacity: 0.9 }, layer);
    }
  }
  requestAnimationFrame(frame);
}

// ================================================================ tabs
function activateTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { activateTab(b.dataset.tab); refreshTabs(true); }));
const lastHtml = {};
function setHTML(id, html) { const e = $("#" + id); if (lastHtml[id] === html) return false; lastHtml[id] = html; e.innerHTML = html; return true; }
function canEdit() { return mode === "live" && !busyIds().length && (STATIC || (CFG && CFG.boot === "ready")); }

function renderHostTab() {
  if (!selected || !activeIds().includes(selected)) {
    selected = null;
    setHTML("tab-host", `<h3>Pick a host</h3><p class="sub">Click any host on the map. Choose what it should do, then launch it. The <b>Scenario…</b> menu fills the whole network. Use <b>+ host</b> / <b>− host</b> inside a client network, and <b>+ Network</b> above the map, to change the topology.</p>
    <div class="help"><b>How to read the map.</b> Each client network has its own switch and hosts. An attacker host replays a slice of the <i>real captured attack</i> through the switches. After its first ${fmt(CFG.window)} packets the cascade (LightGBM classifier, then the client's autoencoder) judges the host and the controller installs a drop rule on the host's switch. ${STATIC ? "On this page the packets are not sent; each verdict is the real cascade output, computed in the project VM for that client's model and capture." : "Packets from a blocked host then show up as dropped counts on the real switch."}</div>`);
    return;
  }
  const h = H(selected), v = h.verdict, m = h.mit, ed = canEdit();
  const roles = ["normal", ...CFG.classes], net = Number(selected.slice(1, selected.indexOf("h"))), host = CFG.hosts.find((x) => x.id === selected);
  const note = NET_NOTE[CFG.bundle_clients ? CFG.bundle_clients[net] : -1];
  let html = `<h3>${selected} <span class="sub">(client ${net}, ${host.ip})</span></h3>${note ? `<p class="sub" style="color:#b45309">⚠ This network's model ${note}.</p>` : ""}
  <p class="sub">What should this host do?${ed ? "" : " (Roles can be changed when no host is running.)"}</p><div class="chips">` +
    roles.map((r) => `<button class="chip ${r === "normal" ? "normal" : ""} ${h.role === r ? "sel" : ""}" data-role="${r}" ${ed ? "" : "disabled"}>${r === "normal" ? "Normal device" : LONG(r)}</button>`).join("") +
    `</div><div class="btnrow"><button class="btn go" id="btn-launch-one" ${ed && h.role !== "idle" ? "" : "disabled"}>Launch this host</button><button class="btn" id="btn-clear-one" ${ed ? "" : "disabled"}>Set idle</button></div>`;
  if (v) {
    const isB = v.stage === "boosting";
    html += `<h3>Verdict</h3><table>
      <tr><td>True role</td><td><b>${v.truth === "normal" ? "Normal" : LONG(v.truth)}</b></td></tr>
      <tr><td>Cascade says</td><td><b>${v.is_attack ? LONG(v.label) : "Normal"}</b> (${pct(v.confidence)} confidence)</td></tr>
      <tr><td>Decided by</td><td><span class="tag ${isB ? "stage-b" : "stage-a"}">${isB ? "Classifier (LightGBM)" : "Autoencoder backstop"}</span></td></tr>
      <tr><td>Packets flagged</td><td>${fmt(v.flagged)} of ${fmt(v.packets)} (${pct(v.share, 1)}). Host is an attacker if at least ${pct(CFG.share_threshold, 0)} are flagged.</td></tr>
      <tr><td>Source</td><td>${v.source === "wire" ? "Real captured packets" + (STATIC ? " (verdict precomputed in the VM)" : " sent through the switches") : "Real held-out normal rows from the dataset"}</td></tr>
      <tr><td>Model time</td><td>${v.source === "wire" ? `features ${v.extract_ms.toFixed(0)} ms + ` : ""}cascade ${v.classify_ms.toFixed(0)} ms for ${fmt(v.packets)} packets</td></tr>
      ${m ? `<tr><td>Network action</td><td><b>${m.action === "block" ? "DROP rule installed" : m.action === "rate_limit" ? "Rate-limited" : v.is_attack ? "Not blocked (confidence below the 50% threshold for any rule)" : "Allowed"}</b>${m.action !== "allow" ? ` (${m.time_to_action_s}s after launch)` : ""}</td></tr>` : ""}
      ${h.dropped ? `<tr><td>Dropped by switch</td><td><b>${fmt(h.dropped)}</b> packets${STATIC ? " (simulated from the send rate)" : " (counted by the switch rule)"}</td></tr>` : ""}
    </table><h3 style="margin-top:12px">What the cascade called each packet</h3>`;
    const tot = v.packets;
    html += v.top.map(([k, n]) => `<div style="font-size:13px">${k === "benign" ? "Normal" : LONG(k)} <span class="sub">${fmt(n)} (${pct(n / tot, 1)})</span></div><div class="bar"><i style="width:${(100 * n) / tot}%"></i></div>`).join("");
    if (v.truth !== "normal" && !v.type_ok && v.is_attack) html += `<div class="help">The attack was detected but named differently from its true type. ${v.truth === "MITM" ? "MITM is a single ARP-spoofing connection; the offline benchmark has the same weakness." : "The offline benchmark reports the same kind of confusion for this class."}</div>`;
  }
  if (setHTML("tab-host", html)) {
    const box = $("#tab-host");
    box.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => setRole(selected, b.dataset.role)));
    const lo = $("#btn-launch-one"); if (lo) lo.onclick = () => launch([selected]);
    const co = $("#btn-clear-one"); if (co) co.onclick = () => setRole(selected, "idle");
  }
}

function renderResults() {
  const s = score();
  const rows = activeIds().map((id) => S.hosts[id]).filter((h) => h && h.verdict).map((h) => {
    const v = h.verdict, okTag = v.truth === "normal" ? (h.mit && h.mit.action === "block" ? '<span class="tag bad">false alarm</span>' : '<span class="tag ok">correct</span>') : (!v.is_attack ? '<span class="tag bad">missed</span>' : !(h.mit && h.mit.action === "block") ? '<span class="tag warn">detected, not blocked</span>' : v.type_ok ? '<span class="tag ok">correct</span>' : '<span class="tag warn">blocked, type differs</span>');
    return `<tr><td><b>${h.id}</b></td><td>${v.truth === "normal" ? "Normal" : LONG(v.truth)}</td><td>${v.is_attack ? LONG(v.label) : "Normal"} <span class="sub">${pct(v.confidence, 1)}</span></td><td><span class="tag ${v.stage === "boosting" ? "stage-b" : "stage-a"}">${v.stage === "boosting" ? "Classifier" : "Autoencoder"}</span></td><td>${h.ttb != null && h.mit && h.mit.action === "block" ? h.ttb + "s" : "-"}</td><td>${okTag}</td></tr>`;
  }).join("");
  setHTML("tab-results", `<h3>Scoreboard for this run</h3>
  <p class="sub">Counted from the hosts you launched. This is a small scenario; the large-scale measurements are in the Benchmark tab.</p>
  <div class="cards">
    <div class="card ${s.attacks && s.atkDetected === s.attacks ? "good" : ""}"><b>${s.atkDetected} / ${s.attacks}</b><span>attacks detected</span></div>
    <div class="card ${s.attacks && s.atkBlocked === s.attacks ? "good" : ""}"><b>${s.atkBlocked} / ${s.attacks}</b><span>attacks blocked by a drop rule</span></div>
    <div class="card"><b>${s.typeOk} / ${s.attacks}</b><span>attack types named correctly</span></div>
    <div class="card ${s.falseBlocks ? "bad" : "good"}"><b>${s.falseBlocks} / ${s.normals}</b><span>normal hosts wrongly blocked</span></div>
    <div class="card"><b>${s.ttb == null ? "-" : s.ttb.toFixed(1) + " s"}</b><span>average time from launch to block</span></div>
    <div class="card"><b>${fmt(s.dropped)}</b><span>packets dropped by switch rules${STATIC ? " (simulated)" : ""}</span></div>
  </div>
  <table><tr><th>Host</th><th>True</th><th>Cascade says</th><th>Stage</th><th>Block time</th><th>Result</th></tr>${rows || '<tr><td colspan="6" class="sub">No verdicts yet.</td></tr>'}</table>
  <div class="help">Time to block = ${fmt(CFG.window)} packets sent at ${fmt(Math.round(CFG.pps * S.speed))} packets/s (speed ${S.speed}x), plus feature extraction, the cascade and the rule install. Mitigation works on windows of packets, not per packet.</div>`);
}
function renderFeed() { setHTML("tab-feed", `<h3>What is happening, step by step</h3><div class="feed">${S.feed.join("") || '<p class="sub">Nothing yet.</p>'}</div>`); }
function renderSwitch() {
  const rows = activeIds().map((id) => S.hosts[id]).filter((h) => h && h.mit && h.mit.action === "block").map((h) => `<tr><td><b>${h.id}</b></td><td>switch s${Number(h.id.slice(1, h.id.indexOf("h"))) + 1}</td><td><code>ipv4_src=${CFG.hosts.find((x) => x.id === h.id).ip} → drop</code></td><td>${fmt(h.dropped || 0)}</td></tr>`).join("");
  setHTML("tab-switch", `<h3>Rules the controller has installed</h3>
  <p class="sub">${STATIC ? "On the live arena these are read from the Open vSwitch flow tables over OpenFlow." : "Read live from the Open vSwitch flow tables over OpenFlow, not from what the bridge believes it sent."}</p>
  <table><tr><th>Host</th><th>Where</th><th>Rule</th><th>Packets hit</th></tr>${rows || '<tr><td colspan="4" class="sub">No mitigation rules yet.</td></tr>'}</table>
  <div class="help">Every switch also has one default rule that forwards normally. A drop rule has higher priority (100), so a blocked host's packets stop at the first switch. Rules are cleared by <b>Reset</b>.</div>`);
}
function renderBench() {
  const b = benchmark; let t = "";
  if (b && b.clients) {
    const map = CFG.bundle_clients || { 1: 1, 2: 2, 3: 3, 4: 7, 5: 8 };
    t = Object.entries(map).map(([k, c]) => {
      const r = b.clients[c]; if (!r) return "";
      const at = Object.values(r.attacks), fb = r.benign.false_block_rate_by_threshold;
      const det = at.length ? at.reduce((a, x) => a + x.detect_rate_by_threshold["0.25"], 0) / at.length : 0, ty = at.length ? at.reduce((a, x) => a + x.type_correct_rate, 0) / at.length : 0;
      return `<tr><td>Client ${k}</td><td>${fmt(r.benign_test_rows)}</td><td>${pct(fb ? fb["0.25"] : 0, 0)}</td><td>${at.length}</td><td>${pct(det, 0)}</td><td>${pct(ty, 0)}</td></tr>`;
    }).join("");
  }
  const p6 = b && b.clients ? pct(b.clients[6].benign.shares_pctiles["50"], 0) : "";
  setHTML("tab-bench", `<h3>Measured offline on held-out data</h3>
  <p class="sub">From the project report. Classifier tested on 397,073 packets from connections never seen in training.</p>
  <div class="cards">
    <div class="card good"><b>99.72%</b><span>classifier accuracy</span></div><div class="card good"><b>0.983</b><span>macro F1 (14 classes)</span></div>
    <div class="card"><b>14 / 14</b><span>real attack captures blocked in Mininet</span></div><div class="card"><b>12 / 14</b><span>of those named with the right type</span></div>
    <div class="card"><b>0.895 to 0.944</b><span>unseen attack types detected by the cascade (classifier alone 0.72 to 0.76)</span></div>
    <div class="card"><b>≥ 0.985</b><span>known-attack recall with up to 50% poisoned clients</span></div>
  </div>
  <h3>Check of the arena's client models</h3>
  <p class="sub">Windows of up to ${fmt(CFG.window)} held-out dataset rows, scored with the same rule as the arena (attacker if at least ${pct(CFG.share_threshold, 0)} flagged). Normal: 200 random windows (fewer distinct windows when the client holds few normal rows). Attacks: 20 windows per class with at least 300 held-out rows.</p>
  <table><tr><th>Arena client</th><th>Normal rows</th><th>Normal windows blocked</th><th>Attack classes</th><th>Detected</th><th>Type right</th></tr>${t}</table>
  <div class="help"><b>Limits, stated plainly.</b> (1) Clients were chosen for well-calibrated anomaly thresholds; the client that flags about ${p6} of its own normal packets (and one with no normal rows) is left out. Networks 7 and 8 use the two weakest remaining models and are marked. (2) Normal hosts use real dataset rows, not packets on the wire: ordinary MQTT traffic made with <code>mosquitto</code> in Mininet was flagged as an attack by the model, which only knows the Edge-IIoTset testbed. (3) MITM and OS fingerprinting are named as another attack type, as in the offline results, and MITM on one network is flagged but not blocked (low confidence). (4) Decisions use a window of ${fmt(CFG.window)} packets, not single packets.</div>`);
}
function refreshTabs(force) {
  const a = document.querySelector(".tabpane.active"); if (!a) return;
  if (force) Object.keys(lastHtml).forEach((k) => delete lastHtml[k]);
  ({ "tab-host": renderHostTab, "tab-results": renderResults, "tab-feed": renderFeed, "tab-switch": renderSwitch, "tab-bench": renderBench })[a.id]();
}

// ================================================================ actions (live: server; hosted: local simulator)
async function api(path, body) {
  if (STATIC) return staticApi(path);
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  return r.json();
}
async function staticApi(path) {
  if (path.startsWith("/api/config")) return (await fetch("config.json")).json();
  if (path === "/api/recordings") return (await fetch("recordings/index.json")).json();
  if (path.startsWith("/api/recordings/")) return (await fetch("recordings/" + path.split("/").pop())).json();
  if (path === "/api/benchmark") return (await fetch("window_benchmark.json")).json();
  return {};
}
const now = () => (performance.now() - simT0) / 1000;
function localEmit(ev) { apply({ t: now(), ...ev }); render(); refreshTabs(); }

async function setRole(host, role) { if (STATIC) { localEmit({ type: "role", host, role }); return; } await api("/api/role", { host, role }); await poll(); }
async function launch(hosts) { if (STATIC) { simLaunch(hosts); return; } await api("/api/launch", { hosts }); await poll(); }
async function topoChange(action, net) {
  if (busyIds().length) return;
  if (STATIC) {
    const t = { ...S.topo };
    if (action === "add_host" && t[net] < CFG.max_hosts) t[net]++;
    else if (action === "remove_host" && t[net] > 1) { localEmit({ type: "role", host: `c${net}h${t[net]}`, role: "idle" }); t[net]--; }
    else if (action === "add_net" && nets().length < CFG.max_nets) t[Math.max(...nets()) + 1] = 3;
    else if (action === "remove_net" && nets().length > 1) { const k = Math.max(...nets()); for (let j = 1; j <= CFG.max_hosts; j++) localEmit({ type: "role", host: `c${k}h${j}`, role: "idle" }); delete t[k]; }
    else return;
    localEmit({ type: "topology", nets: Object.fromEntries(Object.entries(t)) }); return;
  }
  await api("/api/topology", { action, net }); await poll();
}
async function setSpeed(v) { if (STATIC) localEmit({ type: "speed", value: v }); else { await api("/api/speed", { speed: v }); await poll(); } updateSpeedUI(); }

function presetRoles(name) {
  const ids = activeIds(), out = {};
  if (name === "mixed") { const cyc = ["SQL_injection", "normal", "normal", "DDoS_UDP", "normal", "Password", "Backdoor", "normal", "XSS", "normal", "Ransomware", "Port_Scanning", "normal", "Uploading", "DDoS_HTTP"]; ids.forEach((id, i) => (out[id] = cyc[i % cyc.length])); }
  if (name === "all14") ids.forEach((id, i) => (out[id] = i < 14 ? CFG.classes[i] : "normal"));
  if (name === "normal") ids.forEach((id) => (out[id] = "normal"));
  return out;
}
$("#preset").addEventListener("change", async (e) => {
  const name = e.target.value; e.target.value = ""; if (!name || !canEdit()) return;
  for (const [h, r] of Object.entries(presetRoles(name))) { if (STATIC) apply({ t: now(), type: "role", host: h, role: r }); else await api("/api/role", { host: h, role: r }); }
  if (STATIC) { render(); refreshTabs(true); } else await poll();
});
$("#btn-boot").addEventListener("click", async () => { await api("/api/boot", {}); });
$("#btn-launch").addEventListener("click", () => launch("all"));
$("#btn-reset").addEventListener("click", async () => {
  if (STATIC) { simTimers.forEach(clearTimeout); simTimers = []; localEmit({ type: "reset" }); selected = null; refreshTabs(true); return; }
  await api("/api/reset", {}); selected = null; await poll(); refreshTabs(true);
});
$("#btn-addnet").addEventListener("click", () => topoChange("add_net", 0));
$("#btn-rmnet").addEventListener("click", () => topoChange("remove_net", 0));
document.querySelectorAll("#speedbar button").forEach((b) => b.addEventListener("click", () => setSpeed(Number(b.dataset.s))));
function updateSpeedUI() {
  document.querySelectorAll("#speedbar button").forEach((b) => b.classList.toggle("active", Number(b.dataset.s) === S.speed));
  const w = CFG ? CFG.window / (CFG.pps * S.speed) : 3;
  $("#speedinfo").textContent = `a ${fmt(CFG ? CFG.window : 3000)}-packet window takes about ${w.toFixed(w < 10 ? 1 : 0)} s to send`;
}

// ================================================================ simulator (hosted page): real precomputed verdicts, simulated timing
function simLaunch(hosts) {
  if (!V) return;
  const act = new Set(activeIds());
  const ids = (hosts === "all" ? activeIds() : hosts).filter((id) => act.has(id) && S.hosts[id] && S.hosts[id].role !== "idle" && !["sending", "analysing"].includes(S.hosts[id].phase));
  if (!ids.length) return;
  let pending = ids.length;
  const at = (ms, fn) => simTimers.push(setTimeout(fn, ms));
  ids.forEach((id) => {
    const h = S.hosts[id], role = h.role, net = id.slice(1, id.indexOf("h")), speed = S.speed, pps = CFG.pps * speed;
    const rec = V.clients[net];
    const e = role === "normal" ? rec.normal[Math.floor(Math.random() * rec.normal.length)] : rec.classes[role];
    const n = role === "normal" ? e.packets : V.window[role], sendMs = (n / pps) * 1000;
    const wire = role !== "normal", t0 = now();
    localEmit({ type: "launch", host: id, role, client: Number(net), speed, pps });
    const steps = Math.max(2, Math.ceil(sendMs / 400));
    for (let i = 1; i <= steps; i++) at((sendMs * i) / steps, () => localEmit({ type: "progress", host: id, packets: Math.round((n * i) / steps), total: n, source: wire ? "wire" : "dataset" }));
    const anaMs = wire ? e.extract_ms : 0, clsMs = e.classify_ms;
    at(sendMs + 5, () => localEmit({ type: "analysing", host: id }));
    at(sendMs + anaMs + clsMs + 10, () => {
      const attackTruth = role !== "normal";
      localEmit({ type: "verdict", host: id, truth: role, label: e.label, is_attack: e.is_attack, confidence: e.confidence, stage: e.stage, share: e.share, packets: e.packets, flagged: e.flagged, top: e.top,
        detect_ok: e.is_attack === attackTruth, type_ok: attackTruth ? e.label === role : !e.is_attack, extract_ms: e.extract_ms, classify_ms: e.classify_ms, source: wire ? "wire" : "dataset" });
      const tta = Math.round((now() - t0) * 100) / 100;
      localEmit({ type: "mitigation", host: id, action: e.action, applied: true, bridge_ms: 3, time_to_action_s: tta });
      const total = wire ? V.slice[role] : 0, remaining = Math.max(0, total - n - (pps * (anaMs + clsMs)) / 1000);
      const dropMs = e.action === "block" ? (remaining / pps) * 1000 : 0;
      const ticks = Math.max(1, Math.ceil(dropMs / 1000));
      if (e.action === "block") for (let i = 1; i <= ticks; i++) at((dropMs * i) / ticks, () => localEmit({ type: "dropped", host: id, packets: Math.round((remaining * i) / ticks), rule: "drop" }));
      at(Math.max(dropMs, 600) + 400, () => { localEmit({ type: "host_done", host: id }); if (--pending === 0) localEmit({ type: "run_done" }); });
    });
  });
}

// ================================================================ live polling
async function poll() {
  if (STATIC || mode !== "live") return;
  try {
    const d = await api(`/api/events?since=${nextEv}`);
    CFG.boot = d.boot.state;
    d.events.forEach(apply); nextEv = d.next;
    updateChrome(d.boot);
  } catch (e) { /* server restarting */ }
  render(); refreshTabs(); updateSpeedUI();
}
function updateChrome(boot) {
  const p = $("#boot");
  p.textContent = boot.state === "ready" ? "Network ready" : boot.state === "error" ? "Error: " + boot.message : boot.state === "off" ? "Network off" : boot.message;
  p.className = "pill " + (boot.state === "ready" ? "ready" : boot.state === "error" ? "err" : boot.state === "off" ? "" : "busy");
  const ready = boot.state === "ready" && mode === "live";
  $("#btn-boot").disabled = boot.state !== "off" && boot.state !== "error";
  $("#btn-launch").disabled = !ready || busyIds().length > 0 || !activeIds().some((id) => S.hosts[id] && S.hosts[id].phase === "armed");
  $("#btn-reset").disabled = !ready;
  ["#btn-addnet", "#btn-rmnet"].forEach((q) => ($(q).disabled = !ready || busyIds().length > 0));
  document.querySelectorAll("#speedbar button").forEach((b) => (b.disabled = !ready));
}
function updateStaticChrome() {
  if (mode !== "live") return;
  const idle = !busyIds().length;
  $("#btn-launch").disabled = !idle || !activeIds().some((id) => S.hosts[id] && S.hosts[id].phase === "armed");
  $("#btn-reset").disabled = false;
  $("#btn-addnet").disabled = !idle || nets().length >= CFG.max_nets;
  $("#btn-rmnet").disabled = !idle || nets().length <= 1;
  document.querySelectorAll("#speedbar button").forEach((b) => (b.disabled = false));
}

// ================================================================ replay of a saved run
async function playRecording(name) {
  const rec = await api("/api/recordings/" + name);
  clearInterval(replayTimer); simTimers.forEach(clearTimeout); simTimers = []; mode = "replay"; S = freshState(); selected = null; mapSig = "";
  $("#mode").textContent = "REPLAY: " + name.replace(".json", "").replace("run-", ""); $("#mode").className = "pill replay";
  ["#btn-launch", "#btn-reset", "#btn-boot", "#btn-addnet", "#btn-rmnet"].forEach((s) => ($(s).disabled = true));
  document.querySelectorAll("#speedbar button").forEach((b) => (b.disabled = true));
  const evs = rec.events.filter((e) => e.type !== "boot"); let i = 0; const t0 = performance.now();
  S.narr = "Replaying a saved run. The events below happened on the real network.";
  replayTimer = setInterval(() => {
    const t = (performance.now() - t0) / 1000;
    while (i < evs.length && evs[i].t <= t) apply(evs[i++]);
    render(); refreshTabs(); updateSpeedUI();
    if (i >= evs.length) { clearInterval(replayTimer); S.narr = "Replay finished. Choose another run or go back."; render(); }
  }, 100);
  showBackButton();
}
function showBackButton() {
  if ($("#btn-back")) return;
  const b = document.createElement("button"); b.id = "btn-back"; b.className = "btn primary"; b.textContent = STATIC ? "Back to simulator" : "Back to live";
  b.onclick = () => {
    clearInterval(replayTimer); mode = "live"; b.remove();
    S = freshState(Object.fromEntries(Object.entries(CFG.topo || DEFAULT_TOPO).map(([k, v]) => [Number(k), v]))); S.speed = CFG.speed || 1; nextEv = 0; mapSig = "";
    $("#mode").textContent = STATIC ? "SIMULATOR" : "LIVE"; $("#mode").className = "pill live";
    render(true); refreshTabs(true); updateSpeedUI(); if (STATIC) updateStaticChrome(); else poll();
  };
  $(".actions").prepend(b);
}
$("#rec").addEventListener("change", (e) => { const n = e.target.value; e.target.value = ""; if (n) playRecording(n); });
async function loadRecordings() {
  const names = await api("/api/recordings"), sel = $("#rec");
  sel.innerHTML = '<option value="">Replay a recorded real run…</option>' + names.map((n) => {
    const m = n.match(/run-(\d{8})-(\d{6})-(\d+)attack-(\d+)normal/);
    const label = m ? `${m[2].slice(0, 2)}:${m[2].slice(2, 4)}:${m[2].slice(4)}  ·  ${m[3]} attackers, ${m[4]} normal` : n.replace("run-", "").replace(".json", "");
    return `<option value="${n}">${label}</option>`;
  }).join("");
}

// ================================================================ start
(async function init() {
  CFG = await api("/api/config"); CFG.boot = CFG.boot.state;
  S = freshState(Object.fromEntries(Object.entries(CFG.topo || DEFAULT_TOPO).map(([k, v]) => [Number(k), v]))); S.speed = CFG.speed || 1;
  try { benchmark = await api("/api/benchmark"); } catch (e) { benchmark = null; }
  if (STATIC) { try { V = await (await fetch("verdicts.json")).json(); } catch (e) { V = null; } simT0 = performance.now(); }
  render(true); refreshTabs(true); await loadRecordings(); updateSpeedUI();
  if (STATIC) {
    ["#btn-boot", "#boot"].forEach((q) => ($(q).style.display = "none"));
    $("#mode").textContent = "SIMULATOR"; $("#mode").className = "pill live";
    setInterval(updateStaticChrome, 400); updateStaticChrome();
  } else { setInterval(poll, 450); setInterval(loadRecordings, 8000); poll(); }
  requestAnimationFrame(frame);
})();
