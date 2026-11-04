"use strict";
// ---------------------------------------------------------------- constants
const SHORT = { normal: "Normal", idle: "Idle", Backdoor: "Backdoor", DDoS_HTTP: "DDoS HTTP", DDoS_ICMP: "DDoS ICMP", DDoS_TCP: "DDoS TCP",
  DDoS_UDP: "DDoS UDP", Fingerprinting: "Fingerprint", MITM: "MITM", Password: "Password", Port_Scanning: "Port scan",
  Ransomware: "Ransomware", SQL_injection: "SQL inj.", Uploading: "Uploading", Vulnerability_scanner: "Vuln. scan", XSS: "XSS", anomalous: "Anomalous", benign: "Normal" };
const LONG = (s) => (s || "").replace(/_/g, " ");
const C = { idle: "#9aa8bd", send: "#2e75b6", ana: "#e69b00", ok: "#16a34a", bad: "#dc2626", miss: "#7c3aed", warn: "#ea580c" };
const NS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);
const fmt = (n) => Number(n).toLocaleString("en-US");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";

let CFG = null, S = freshState(), mode = "live", nextEv = 0, selected = null, replayTimer = null, benchmark = null, switchRules = {};
const hostPos = {}, dots = [];

function freshState() { return { hosts: {}, feed: [], narr: "" }; }
function H(id) { return S.hosts[id] || (S.hosts[id] = { id, role: "idle", phase: "idle", packets: 0, total: 0, source: null, verdict: null, mit: null, dropped: 0, ttb: null }); }

// ---------------------------------------------------------------- reducer (live events and recordings share it)
function apply(ev) {
  const stamp = ev.t.toFixed(1).padStart(5, " ");
  const feed = (html) => S.feed.unshift(`<div><span class="t">${stamp}s</span>${html}</div>`);
  switch (ev.type) {
    case "boot": S.narr = "Network is up: 6 switches, 5 client networks, 15 hosts, one controller."; break;
    case "reset": S = freshState(); S.narr = "Reset. All rules cleared. Give the hosts new roles."; break;
    case "role": { const h = H(ev.host); Object.assign(h, { role: ev.role, phase: ev.role === "idle" ? "idle" : "armed", verdict: null, mit: null, packets: 0, dropped: 0, ttb: null }); break; }
    case "launch": { S.narr = `${ev.host} launched as ${ev.role === "normal" ? "a normal device" : LONG(ev.role)}. Window of ${fmt(CFG.window)} packets is being collected.`; const h = H(ev.host); Object.assign(h, { role: ev.role, phase: "sending", packets: 0, total: 0, verdict: null, mit: null, dropped: 0, ttb: null });
      feed(ev.role === "normal" ? `<b>${ev.host}</b> starts as a <b>normal</b> device (scored on real normal rows from the dataset).`
        : `<b>${ev.host}</b> starts a real <b>${LONG(ev.role)}</b> attack: replaying captured packets through its switch.`); break; }
    case "progress": { const h = H(ev.host); Object.assign(h, { packets: ev.packets, total: ev.total, source: ev.source }); break; }
    case "analysing": { const h = H(ev.host); h.phase = "analysing"; S.narr = `${ev.host}: window complete. The cascade is judging it now.`; feed(`<b>${ev.host}</b>: window complete, running the cascade.`); break; }
    case "verdict": { const h = H(ev.host); h.verdict = ev; S.narr = ev.is_attack ? `${ev.host} judged an attacker: ${LONG(ev.label)} (${pct(ev.confidence)}). Sending the verdict to the controller.` : `${ev.host} judged normal (${pct(ev.share, 1)} of packets flagged). No rule installed.`;
      const stage = ev.stage === "boosting" ? "the classifier (LightGBM)" : "the autoencoder backstop";
      if (ev.is_attack) feed(`<b>${ev.host}</b> judged an <b>attacker: ${LONG(ev.label)}</b> (${pct(ev.confidence)}), ${pct(ev.share, 0)} of ${fmt(ev.packets)} packets flagged by ${stage}. ${ev.truth === "normal" ? '<span class="tag warn">false alarm</span>' : ev.type_ok ? '<span class="tag ok">type correct</span>' : '<span class="tag warn">type differs from truth</span>'}`);
      else feed(`<b>${ev.host}</b> judged <b>normal</b>: only ${pct(ev.share, 1)} of ${fmt(ev.packets)} packets flagged. ${ev.truth === "normal" ? '<span class="tag ok">correct</span>' : '<span class="tag bad">missed attack</span>'}`);
      break; }
    case "mitigation": { const h = H(ev.host); h.mit = ev; h.ttb = ev.time_to_action_s; h.phase = "mitigated";
      if (ev.action === "block") { feed(`Controller installed a <b>DROP rule</b> for <b>${ev.host}</b> on its switch (${ev.time_to_action_s}s after launch).`); S.narr = `${ev.host} blocked ${ev.time_to_action_s}s after it started.`; }
      else if (ev.action === "rate_limit") feed(`Controller <b>rate-limited</b> ${ev.host} (confidence below the block threshold).`);
      break; }
    case "dropped": { H(ev.host).dropped = ev.packets; break; }
    case "host_done": { const h = H(ev.host); if (h.phase !== "idle") h.phase = "done"; break; }
    case "run_done": feed("<b>Run finished.</b> See the Results tab for the scoreboard."); S.narr = "Run finished. Results are in the Results tab."; break;
    case "error": feed(`<span class="tag bad">error</span> ${ev.host || ""} ${ev.message}`); break;
  }
}

// ---------------------------------------------------------------- derived state
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
function hostColor(h) {
  const st = hostStatus(h);
  return h.phase === "idle" ? C.idle : st.c;
}
function score() {
  const vs = Object.values(S.hosts).filter((h) => h.verdict);
  const atk = vs.filter((h) => h.verdict.truth !== "normal"), nor = vs.filter((h) => h.verdict.truth === "normal");
  const blocked = vs.filter((h) => h.mit && h.mit.action === "block" && h.mit.time_to_action_s != null);
  return {
    tested: vs.length, detectOk: vs.filter((h) => h.verdict.detect_ok).length, atkBlocked: atk.filter((h) => h.mit && h.mit.action === "block").length,
    attacks: atk.length, atkDetected: atk.filter((h) => h.verdict.is_attack).length, typeOk: atk.filter((h) => h.verdict.type_ok).length,
    normals: nor.length, falseBlocks: nor.filter((h) => h.verdict.is_attack).length, missed: atk.filter((h) => !h.verdict.is_attack).length,
    ttb: blocked.length ? blocked.reduce((a, h) => a + h.mit.time_to_action_s, 0) / blocked.length : null,
    dropped: Object.values(S.hosts).reduce((a, h) => a + (h.dropped || 0), 0),
  };
}

// ---------------------------------------------------------------- map
function el(tag, attrs = {}, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function text(parent, x, y, s, attrs = {}) { const t = el("text", { x, y, "text-anchor": "middle", ...attrs }, parent); t.textContent = s; return t; }
const SW_X = [118, 354, 590, 826, 1062], SW_Y = 262, CORE = { x: 590, y: 150 }, CTRL = { x: 590, y: 42 };

function buildMap() {
  const svg = $("#map"); svg.innerHTML = "";
  const defs = el("defs", {}, svg);
  const g = el("g", {}, svg);
  // control channel
  el("line", { x1: CTRL.x, y1: CTRL.y + 24, x2: CORE.x, y2: CORE.y - 20, stroke: "#9aa8bd", "stroke-width": 2, "stroke-dasharray": "5 5" }, g);
  text(g, CTRL.x + 78, 108, "OpenFlow control", { "font-size": 12, fill: "#5b6b85", "text-anchor": "start" });
  for (let i = 0; i < 5; i++) {
    el("line", { x1: CORE.x, y1: CORE.y + 20, x2: SW_X[i], y2: SW_Y - 18, stroke: "#b8c4d8", "stroke-width": 3 }, g);
    el("line", { x1: CTRL.x - 60 + i * 30, y1: CTRL.y + 24, x2: SW_X[i], y2: SW_Y - 18, stroke: "#dbe3ef", "stroke-width": 1.2, "stroke-dasharray": "3 6" }, g);
  }
  // controller
  const c = el("g", {}, g);
  el("rect", { x: CTRL.x - 150, y: CTRL.y - 24, width: 300, height: 48, rx: 12, fill: "#1f3864" }, c);
  text(c, CTRL.x, CTRL.y - 3, "SDN controller + mitigation bridge", { fill: "#fff", "font-size": 15, "font-weight": 700 });
  text(c, CTRL.x, CTRL.y + 14, "installs drop / rate-limit rules", { fill: "#cadcfc", "font-size": 12 });
  // core
  el("rect", { x: CORE.x - 85, y: CORE.y - 20, width: 170, height: 40, rx: 10, fill: "#e8eefb", stroke: "#2e75b6", "stroke-width": 2 }, g);
  text(g, CORE.x, CORE.y + 5, "Core switch", { "font-size": 14, "font-weight": 700, fill: "#1f3864" });
  // client networks
  for (let i = 0; i < 5; i++) {
    const cx = SW_X[i], k = i + 1;
    el("rect", { x: cx - 115, y: SW_Y + 36, width: 230, height: 262, rx: 16, fill: "#f4f7fb", stroke: "#dbe3ef", "stroke-width": 1.5 }, g);
    el("rect", { x: cx - 58, y: SW_Y - 18, width: 116, height: 36, rx: 9, fill: "#e8eefb", stroke: "#2e75b6", "stroke-width": 1.5 }, g);
    text(g, cx, SW_Y + 5, `Switch s${k + 1}`, { "font-size": 13, "font-weight": 600, fill: "#1f3864" });
    text(g, cx, SW_Y + 36 + 262 - 40, `Client ${k} network`, { "font-size": 16, "font-weight": 700, fill: "#14213d" });
    text(g, cx, SW_Y + 36 + 262 - 20, "own model scaler + threshold", { "font-size": 12, fill: "#5b6b85" });
    for (let j = 1; j <= 3; j++) {
      const id = `c${k}h${j}`, hx = cx + (j - 2) * 74, hy = SW_Y + 112;
      hostPos[id] = { x: hx, y: hy, sx: cx, sy: SW_Y + 18 };
      el("line", { x1: hx, y1: hy - 26, x2: cx, y2: SW_Y + 18, stroke: "#b8c4d8", "stroke-width": 2, id: `link-${id}` }, g);
    }
  }
  const layer = el("g", { id: "hostlayer" }, svg);
  el("g", { id: "dotlayer" }, svg);
  render();
}

function render() {
  const layer = $("#hostlayer"); if (!layer) return;
  layer.innerHTML = "";
  for (const id in hostPos) {
    const h = H(id), p = hostPos[id], col = hostColor(h), st = hostStatus(h);
    const g = el("g", { class: "host", transform: `translate(${p.x},${p.y})` }, layer);
    g.addEventListener("click", () => { selected = id; activateTab("host"); renderHostTab(); render(); });
    if (h.phase === "sending") el("circle", { class: "ring", cx: 0, cy: 0, r: 28, stroke: col }, g);
    if (selected === id) el("circle", { cx: 0, cy: 0, r: 33, fill: "none", stroke: "#1f3864", "stroke-width": 2, "stroke-dasharray": "4 4" }, g);
    el("circle", { class: "body", cx: 0, cy: 0, r: 25, fill: h.phase === "idle" ? "#fff" : col, stroke: col, "stroke-width": 3 }, g);
    const mono = h.phase === "idle" ? C.idle : "#fff";
    // monitor icon
    el("rect", { x: -11, y: -10, width: 22, height: 15, rx: 2.5, fill: "none", stroke: mono, "stroke-width": 2 }, g);
    el("line", { x1: -6, y1: 10, x2: 6, y2: 10, stroke: mono, "stroke-width": 2 }, g);
    if (h.phase === "analysing") el("circle", { class: "spin", cx: 0, cy: 0, r: 31, fill: "none", stroke: C.ana, "stroke-width": 3, "stroke-dasharray": "22 60" }, g);
    if (h.mit && h.mit.action === "block") { el("circle", { cx: 18, cy: -18, r: 10, fill: C.bad, stroke: "#fff", "stroke-width": 2 }, g); text(g, 18, -13.5, "✖", { fill: "#fff", "font-size": 12, "font-weight": 700 }); }
    text(g, 0, 45, id, { "font-size": 14, "font-weight": 700, fill: "#14213d" });
    // role chip
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
    // link colour
    const lk = $(`#link-${id}`); if (lk) { const blocked = h.mit && h.mit.action === "block"; lk.setAttribute("stroke", blocked ? C.bad : h.phase === "sending" ? C.send : "#b8c4d8"); lk.setAttribute("stroke-dasharray", blocked ? "6 5" : ""); lk.setAttribute("stroke-width", blocked || h.phase === "sending" ? 3 : 2); }
  }
  $("#narr").textContent = S.narr || "Start the network, give each host a role (click a host), then launch.";
}

// packet animation (illustrative: dots only show that traffic flows; counts elsewhere are real)
let lastSpawn = 0;
function frame(ts) {
  const layer = $("#dotlayer");
  if (layer) {
    if (ts - lastSpawn > 140) {
      lastSpawn = ts;
      for (const id in S.hosts) {
        const h = S.hosts[id];
        if (h.phase === "sending") dots.push({ id, p: 0, c: h.source === "dataset" ? "#16a34a" : "#dc2626", dead: false });
        else if (h.mit && h.mit.action === "block" && h.dropped && h.phase !== "idle" && h.phase !== "armed") dots.push({ id, p: 0, c: "#dc2626", blocked: true });
      }
    }
    layer.innerHTML = "";
    for (let i = dots.length - 1; i >= 0; i--) {
      const d = dots[i], pos = hostPos[d.id]; d.p += d.blocked ? 0.035 : 0.028;
      if (d.p > 1 || !pos) { dots.splice(i, 1); continue; }
      let x, y;
      if (d.blocked) { const q = Math.min(1, d.p / 0.5); x = pos.x + (pos.sx - pos.x) * q; y = pos.y - 26 + (pos.sy - (pos.y - 26)) * q; if (d.p > 0.5) { dots.splice(i, 1); continue; } }
      else if (d.p < 0.5) { const q = d.p / 0.5; x = pos.x + (pos.sx - pos.x) * q; y = pos.y - 26 + (pos.sy - (pos.y - 26)) * q; }
      else { const q = (d.p - 0.5) / 0.5; x = pos.sx + (CORE.x - pos.sx) * q; y = pos.sy + (CORE.y + 20 - pos.sy) * q; }
      el("circle", { cx: x, cy: y, r: 4, fill: d.c, opacity: 0.9 }, layer);
    }
  }
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- tabs
function activateTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { activateTab(b.dataset.tab); refreshTabs(); }));

function renderHostTab() {
  const box = $("#tab-host");
  if (!selected) { box.innerHTML = `<h3>Pick a host</h3><p class="sub">Click any of the 15 hosts on the map. ${STATIC ? "Its verdict from the recorded run appears here." : "Choose what it should do, then launch it. You can also use <b>Scenario…</b> at the top to fill the whole network."}</p>
    <div class="help"><b>How to read the map.</b> Each client network has its own switch and three hosts. An attacker host replays a slice of the <i>real captured attack</i> through the switches. After its first ${fmt(CFG.window)} packets the cascade (LightGBM classifier, then the client's autoencoder) judges the host and the controller installs a drop rule on the host's switch. Packets from a blocked host then show up as dropped counts on the real switch.</div>`; return; }
  const h = H(selected), busy = ["sending", "analysing"].includes(h.phase), v = h.verdict, m = h.mit;
  const canEdit = mode === "live" && !busy && CFG.boot === "ready";
  const roles = ["normal", ...CFG.classes];
  let html = `<h3>${selected} <span class="sub">(client ${selected[1]}, ${CFG.hosts.find((x) => x.id === selected).ip})</span></h3>
  <p class="sub">What should this host do?</p><div class="chips">` +
    roles.map((r) => `<button class="chip ${r === "normal" ? "normal" : ""} ${h.role === r ? "sel" : ""}" data-role="${r}" ${canEdit ? "" : "disabled"}>${r === "normal" ? "Normal device" : LONG(r)}</button>`).join("") +
    `</div><div class="btnrow"><button class="btn go" id="btn-launch-one" ${canEdit && h.role !== "idle" ? "" : "disabled"}>Launch this host</button><button class="btn" id="btn-clear-one" ${canEdit ? "" : "disabled"}>Set idle</button></div>`;
  if (v) {
    const isB = v.stage === "boosting";
    html += `<h3>Verdict</h3><table>
      <tr><td>True role</td><td><b>${v.truth === "normal" ? "Normal" : LONG(v.truth)}</b></td></tr>
      <tr><td>Cascade says</td><td><b>${v.is_attack ? LONG(v.label) : "Normal"}</b> (${pct(v.confidence)} confidence)</td></tr>
      <tr><td>Decided by</td><td><span class="tag ${isB ? "stage-b" : "stage-a"}">${isB ? "Classifier (LightGBM)" : "Autoencoder backstop"}</span></td></tr>
      <tr><td>Packets flagged</td><td>${fmt(v.flagged)} of ${fmt(v.packets)} (${pct(v.share, 1)}). Host is an attacker if at least ${pct(CFG.share_threshold, 0)} are flagged.</td></tr>
      <tr><td>Source</td><td>${v.source === "wire" ? "Real captured packets sent through the switches" : "Real held-out normal rows from the dataset"}</td></tr>
      <tr><td>Model time</td><td>${v.source === "wire" ? `features ${v.extract_ms.toFixed(0)} ms + ` : ""}cascade ${v.classify_ms.toFixed(0)} ms for ${fmt(v.packets)} packets</td></tr>
      ${m ? `<tr><td>Network action</td><td><b>${m.action === "block" ? "DROP rule installed" : m.action === "rate_limit" ? "Rate-limited" : v.is_attack ? "Not blocked (confidence below the 85% block threshold)" : "Allowed"}</b>${m.action !== "allow" ? ` (${m.time_to_action_s}s after launch)` : ""}</td></tr>` : ""}
      ${h.dropped ? `<tr><td>Dropped by switch</td><td><b>${fmt(h.dropped)}</b> packets (counted by the switch rule)</td></tr>` : ""}
    </table><h3 style="margin-top:12px">What the cascade called each packet</h3>`;
    const tot = v.packets;
    html += v.top.map(([k, n]) => `<div style="font-size:13px">${k === "benign" ? "Normal" : LONG(k)} <span class="sub">${fmt(n)} (${pct(n / tot, 1)})</span></div><div class="bar"><i style="width:${(100 * n) / tot}%"></i></div>`).join("");
    if (v.truth !== "normal" && !v.type_ok) html += `<div class="help">The attack was detected and blocked but named differently from its true type. ${v.truth === "MITM" ? "MITM is a single ARP-spoofing connection; the offline benchmark has the same weakness (it cannot be scored on held-out connections)." : "The offline benchmark reports the same kind of confusion for this class."}</div>`;
  }
  box.innerHTML = html;
  box.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => setRole(selected, b.dataset.role)));
  const lo = $("#btn-launch-one"); if (lo) lo.onclick = () => launch([selected]);
  const co = $("#btn-clear-one"); if (co) co.onclick = () => setRole(selected, "idle");
}

function renderResults() {
  const s = score(), box = $("#tab-results");
  const rows = Object.values(S.hosts).filter((h) => h.verdict).map((h) => {
    const v = h.verdict, okTag = v.truth === "normal" ? (v.is_attack ? '<span class="tag bad">false alarm</span>' : '<span class="tag ok">correct</span>') : (!v.is_attack ? '<span class="tag bad">missed</span>' : !(h.mit && h.mit.action === "block") ? '<span class="tag warn">detected, not blocked</span>' : v.type_ok ? '<span class="tag ok">correct</span>' : '<span class="tag warn">blocked, type differs</span>');
    return `<tr><td><b>${h.id}</b></td><td>${v.truth === "normal" ? "Normal" : LONG(v.truth)}</td><td>${v.is_attack ? LONG(v.label) : "Normal"} <span class="sub">${pct(v.confidence, 1)}</span></td><td><span class="tag ${v.stage === "boosting" ? "stage-b" : "stage-a"}">${v.stage === "boosting" ? "Classifier" : "Autoencoder"}</span></td><td>${h.ttb != null && v.is_attack ? h.ttb + "s" : "-"}</td><td>${okTag}</td></tr>`;
  }).join("");
  box.innerHTML = `<h3>Scoreboard for this run</h3>
  <p class="sub">Counted from the hosts you launched. This is a small live scenario; the large-scale measurements are in the Benchmark tab.</p>
  <div class="cards">
    <div class="card ${s.attacks && s.atkDetected === s.attacks ? "good" : ""}"><b>${s.atkDetected} / ${s.attacks}</b><span>attacks detected</span></div>
    <div class="card ${s.attacks && s.atkBlocked === s.attacks ? "good" : ""}"><b>${s.atkBlocked} / ${s.attacks}</b><span>attacks blocked by a drop rule</span></div>
    <div class="card"><b>${s.typeOk} / ${s.attacks}</b><span>attack types named correctly</span></div>
    <div class="card ${s.falseBlocks ? "bad" : "good"}"><b>${s.falseBlocks} / ${s.normals}</b><span>normal hosts wrongly blocked</span></div>
    <div class="card"><b>${s.ttb == null ? "-" : s.ttb.toFixed(1) + " s"}</b><span>average time from launch to block</span></div>
    <div class="card"><b>${fmt(s.dropped)}</b><span>packets dropped by switch rules</span></div>
  </div>
  <table><tr><th>Host</th><th>True</th><th>Cascade says</th><th>Stage</th><th>Block time</th><th>Result</th></tr>${rows || '<tr><td colspan="6" class="sub">No verdicts yet.</td></tr>'}</table>
  <div class="help">Time to block = ${fmt(CFG.window)} packets sent at ${fmt(CFG.pps)} packets/s, plus feature extraction, the cascade and the rule install. Mitigation works on windows of packets, not per packet.</div>`;
}

function renderFeed() { $("#tab-feed").innerHTML = `<h3>What is happening, step by step</h3><div class="feed">${S.feed.join("") || '<p class="sub">Nothing yet.</p>'}</div>`; }

function renderSwitch() {
  const rows = Object.values(S.hosts).filter((h) => h.mit && h.mit.action === "block").map((h) => `<tr><td><b>${h.id}</b></td><td>switch s${Number(h.id[1]) + 1}</td><td><code>ipv4_src=${CFG.hosts.find((x) => x.id === h.id).ip} → drop</code></td><td>${fmt(h.dropped || 0)}</td></tr>`).join("");
  $("#tab-switch").innerHTML = `<h3>Rules the controller has installed</h3>
  <p class="sub">Read live from the Open vSwitch flow tables over OpenFlow, not from what the bridge believes it sent.</p>
  <table><tr><th>Host</th><th>Where</th><th>Rule</th><th>Packets hit</th></tr>${rows || '<tr><td colspan="4" class="sub">No mitigation rules yet.</td></tr>'}</table>
  <div class="help">Every switch also has one default rule that forwards normally. A drop rule has higher priority (100), so a blocked host's packets stop at the first switch. Rules are cleared by <b>Reset</b>.</div>`;
}

function renderBench() {
  const b = benchmark; let t = "";
  if (b && b.clients) {
    const map = { 1: 1, 2: 2, 3: 3, 4: 7, 5: 8 };
    t = Object.entries(map).map(([k, c]) => {
      const r = b.clients[c], at = Object.values(r.attacks), fb = r.benign.false_block_rate_by_threshold;
      const det = at.length ? at.reduce((a, x) => a + x.detect_rate_by_threshold["0.25"], 0) / at.length : 0, ty = at.length ? at.reduce((a, x) => a + x.type_correct_rate, 0) / at.length : 0;
      return `<tr><td>Client ${k}</td><td>${fmt(r.benign_test_rows)}</td><td>${pct(fb ? fb["0.25"] : 0, 0)}</td><td>${at.length}</td><td>${pct(det, 0)}</td><td>${pct(ty, 0)}</td></tr>`;
    }).join("");
  }
  const p6 = b && b.clients ? pct(b.clients[6].benign.shares_pctiles["50"], 0) : "", p9 = b && b.clients ? pct(b.clients[9].benign.shares_pctiles["50"], 0) : "";
  $("#tab-bench").innerHTML = `<h3>Measured offline on held-out data</h3>
  <p class="sub">From the project report. Classifier tested on 397,073 packets from connections never seen in training.</p>
  <div class="cards">
    <div class="card good"><b>99.72%</b><span>classifier accuracy</span></div><div class="card good"><b>0.983</b><span>macro F1 (14 classes)</span></div>
    <div class="card"><b>14 / 14</b><span>real attack captures blocked in Mininet</span></div><div class="card"><b>12 / 14</b><span>of those named with the right type</span></div>
    <div class="card"><b>0.895 to 0.944</b><span>unseen attack types detected by the cascade (classifier alone 0.72 to 0.76)</span></div>
    <div class="card"><b>≥ 0.985</b><span>known-attack recall with up to 50% poisoned clients</span></div>
  </div>
  <h3>Check of this arena's five client models</h3>
  <p class="sub">Windows of ${fmt(CFG.window)} held-out dataset rows, scored with the same rule as the live arena (attacker if at least ${pct(CFG.share_threshold, 0)} flagged). Normal: 200 random windows of up to ${fmt(CFG.window)} rows (fewer when the client holds fewer normal rows). Attacks: 20 windows per class that has at least 300 held-out rows.</p>
  <table><tr><th>Arena client</th><th>Normal rows</th><th>Normal windows blocked</th><th>Attack classes</th><th>Detected</th><th>Type right</th></tr>${t}</table>
  <div class="help"><b>Limits, stated plainly.</b> (1) These five clients were chosen because their anomaly threshold is well calibrated; two other clients (6 and 9) flag about ${p6} and ${p9} of their own normal packets, so they are left out. (2) Normal hosts use real dataset rows, not packets on the wire: ordinary MQTT traffic made with <code>mosquitto</code> in Mininet was flagged as an attack by the model, which only knows the Edge-IIoTset testbed. (3) MITM and OS fingerprinting are blocked but named as another attack type, as in the offline results. (4) Host decisions use a window of ${fmt(CFG.window)} packets, not single packets.</div>`;
}

function refreshTabs() {
  const a = document.querySelector(".tabpane.active"); if (!a) return;
  ({ "tab-host": renderHostTab, "tab-results": renderResults, "tab-feed": renderFeed, "tab-switch": renderSwitch, "tab-bench": renderBench })[a.id]();
}

// ---------------------------------------------------------------- API
const STATIC = !!window.ARENA_STATIC;
async function staticApi(path) {
  if (path.startsWith("/api/config")) return (await fetch("config.json")).json();
  if (path === "/api/recordings") return (await fetch("recordings/index.json")).json();
  if (path.startsWith("/api/recordings/")) return (await fetch("recordings/" + path.split("/").pop())).json();
  if (path === "/api/benchmark") return (await fetch("window_benchmark.json")).json();
  if (path.startsWith("/api/events")) return { events: [], next: 0, boot: { state: "static", message: "Recorded runs" }, busy: [] };
  return {};
}
async function api(path, body) {
  if (STATIC) return staticApi(path);
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  return r.json();
}
async function setRole(host, role) { await api("/api/role", { host, role }); await poll(); }
async function launch(hosts) { await api("/api/launch", { hosts }); await poll(); }

const PRESETS = {
  mixed: { c1h1: "SQL_injection", c1h2: "normal", c1h3: "normal", c2h1: "DDoS_UDP", c2h2: "normal", c2h3: "Password", c3h1: "Backdoor", c3h2: "normal", c3h3: "XSS",
    c4h1: "normal", c4h2: "Ransomware", c4h3: "Port_Scanning", c5h1: "normal", c5h2: "Uploading", c5h3: "DDoS_HTTP" },
};
function presetRoles(name) {
  if (name === "mixed") return PRESETS.mixed;
  const ids = CFG.hosts.map((h) => h.id), out = {};
  if (name === "all14") ids.forEach((id, i) => (out[id] = i < 14 ? CFG.classes[i] : "normal"));
  if (name === "normal") ids.forEach((id) => (out[id] = "normal"));
  return out;
}
$("#preset").addEventListener("change", async (e) => {
  const name = e.target.value; e.target.value = ""; if (!name || mode !== "live") return;
  for (const [h, r] of Object.entries(presetRoles(name))) await api("/api/role", { host: h, role: r });
  await poll();
});
$("#btn-boot").addEventListener("click", async () => { await api("/api/boot", {}); });
$("#btn-launch").addEventListener("click", () => launch("all"));
$("#btn-reset").addEventListener("click", async () => { await api("/api/reset", {}); selected = null; await poll(); renderHostTab(); });

async function poll() {
  if (mode !== "live") return;
  try {
    const d = await api(`/api/events?since=${nextEv}`);
    CFG.boot = d.boot.state;
    d.events.forEach(apply); nextEv = d.next;
    updateChrome(d.boot, d.busy);
    switchRules = await api("/api/switch");
  } catch (e) { /* server restarting */ }
  render(); refreshTabs();
}
function updateChrome(boot, busy) {
  const p = $("#boot");
  p.textContent = boot.state === "ready" ? "Network ready" : boot.state === "error" ? "Error: " + boot.message : boot.state === "off" ? "Network off" : boot.message;
  p.className = "pill " + (boot.state === "ready" ? "ready" : boot.state === "error" ? "err" : boot.state === "off" ? "" : "busy");
  const ready = boot.state === "ready" && mode === "live";
  $("#btn-boot").disabled = boot.state !== "off" && boot.state !== "error";
  $("#btn-launch").disabled = !ready || (busy && busy.length > 0) || !Object.values(S.hosts).some((h) => h.phase === "armed");
  $("#btn-reset").disabled = !ready;
}

// ---------------------------------------------------------------- replay of a saved run
async function playRecording(name) {
  const rec = await api("/api/recordings/" + name);
  clearInterval(replayTimer); mode = "replay"; S = freshState(); selected = null;
  $("#mode").textContent = "REPLAY: " + name.replace(".json", ""); $("#mode").className = "pill replay";
  ["#btn-launch", "#btn-reset", "#btn-boot"].forEach((s) => ($(s).disabled = true));
  const evs = rec.events.filter((e) => e.type !== "boot"); let i = 0; const t0 = performance.now();
  S.narr = "Replaying a saved live run. The events below happened on the real network.";
  replayTimer = setInterval(() => {
    const now = (performance.now() - t0) / 1000;
    while (i < evs.length && evs[i].t <= now) apply(evs[i++]);
    render(); refreshTabs();
    if (i >= evs.length) { clearInterval(replayTimer); S.narr = "Replay finished. Choose another run, or click a host to see its verdict."; render(); showBackButton(); }
  }, 100);
  showBackButton();
}
function showBackButton() {
  if (STATIC || $("#btn-back")) return;
  const b = document.createElement("button"); b.id = "btn-back"; b.className = "btn primary"; b.textContent = "Back to live";
  b.onclick = () => { clearInterval(replayTimer); mode = "live"; b.remove(); $("#mode").textContent = "LIVE"; $("#mode").className = "pill live"; S = freshState(); nextEv = 0; poll(); };
  $(".actions").prepend(b);
}
$("#rec").addEventListener("change", (e) => { const n = e.target.value; e.target.value = ""; if (n) playRecording(n); });
async function loadRecordings() {
  const names = await api("/api/recordings"), sel = $("#rec");
  sel.innerHTML = '<option value="">Replay a saved run…</option>' + names.map((n) => { const m = n.match(/run-(\d{8})-(\d{6})-(\d+)attack-(\d+)normal/); const label = m ? `${m[2].slice(0, 2)}:${m[2].slice(2, 4)}:${m[2].slice(4)}  ·  ${m[3]} attackers, ${m[4]} normal` : n.replace("run-", "").replace(".json", ""); return `<option value="${n}">${label}</option>`; }).join("");
}

// ---------------------------------------------------------------- start
(async function init() {
  CFG = await api("/api/config"); CFG.boot = CFG.boot.state;
  try { benchmark = await api("/api/benchmark"); } catch (e) { benchmark = null; }
  buildMap(); refreshTabs(); await loadRecordings();
  if (STATIC) {
    ["#btn-boot", "#preset", "#btn-launch", "#btn-reset"].forEach((q) => ($(q).style.display = "none"));
    $("#boot").style.display = "none";
    const opts = [...document.querySelectorAll("#rec option")].map((o) => o.value).filter(Boolean);
    const first = opts.find((n) => n.includes("14attack")) || opts[0];
    if (first) playRecording(first);
  }
  setInterval(poll, 450); setInterval(loadRecordings, 8000);
  requestAnimationFrame(frame); poll();
})();
