"""Live arena server: the web UI plus the orchestration behind it.

Run (non-root, inside the VM):  venv/bin/python -m fl_ids.arena.server      ->  http://127.0.0.1:8090

Boot starts the existing SDN bridge + OpenFlow controller (fl_ids.sdn.bridge) and the root network agent
(fl_ids.arena.netagent, 5 client networks x 3 hosts). A host with an attack role replays a slice of the real
capture for that attack through the switches; after its first window of packets the cascade classifies it and the
verdict goes to the bridge, which installs the drop / rate-limit rule. A host with the Normal role is scored on
real held-out normal rows from the dataset (generic MQTT made with mosquitto is flagged as an attack by the
model, so it can't stand in for the dataset's own normal traffic).

Every state change is an event; the UI is a reducer over the event list, so a saved list replays as a recording.
"""

from __future__ import annotations

import json
import logging
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import requests
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fl_ids.arena.verdict import SHARE_THRESHOLD, WINDOW_PACKETS, window_verdict  # noqa: E402

logger = logging.getLogger("arena")
ASSETS = ROOT / "arena_assets"
SLICES = ASSETS / "slices"
RECORDINGS = ASSETS / "recordings"
STATIC = Path(__file__).parent / "static"
BRIDGE = "http://127.0.0.1:8080"
AGENT = "http://127.0.0.1:8099"
PPS = 1000
BUNDLE = ROOT / "saved_models" / "full" / "c10_s42"
# Arena client k (1..5) uses these clients of the 10-client bundle: those with well-calibrated anomaly thresholds
# on their own held-out normal traffic (see arena_assets/window_benchmark.json); clients 6 and 9 flag 17-26% of it.
BUNDLE_CLIENTS = {1: 1, 2: 2, 3: 3, 4: 7, 5: 8}
CLASSES = ["Backdoor", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP", "Fingerprinting", "MITM", "Password",
           "Port_Scanning", "Ransomware", "SQL_injection", "Uploading", "Vulnerability_scanner", "XSS"]

app = Flask(__name__, static_folder=None)
LOCK = threading.Lock()
CLS_LOCK = threading.Lock()
EVENTS: list[dict] = []
T0 = time.time()
HOSTS: list[dict] = [
    {"id": f"c{k}h{j}", "client": k, "bundle_client": BUNDLE_CLIENTS[k], "ip": f"10.0.{k}.{j}"}
    for k in range(1, 6) for j in range(1, 4)
]
HOST = {h["id"]: h for h in HOSTS}
ROLES: dict[str, str] = {h["id"]: "idle" for h in HOSTS}
BUSY: set[str] = set()
TX: dict[str, int] = {}
SENDING: dict[str, bool] = {}
SWITCH_DROPS: dict[str, dict] = {}
BOOT = {"state": "off", "message": "Network not started"}
CTX: dict = {}
RUN_LAUNCHED = 0
procs: dict[str, subprocess.Popen] = {}


def emit(kind: str, **kw) -> None:
    with LOCK:
        EVENTS.append({"i": len(EVENTS), "t": round(time.time() - T0, 3), "type": kind, **kw})


def count_packets(path: Path) -> int:
    with open(path, "rb") as f:
        gh = f.read(24)
        endian = "<" if gh[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        n = 0
        while True:
            h = f.read(16)
            if len(h) < 16:
                return n
            f.seek(struct.unpack(endian + "IIII", h)[2], 1)
            n += 1


def agent(method: str, path: str, **body):
    r = requests.request(method, AGENT + path, json=body or None, timeout=15)
    return r.json()


# ------------------------------------------------------------------ boot
def boot_worker() -> None:
    try:
        BOOT.update(state="starting", message="Starting the SDN controller and bridge")
        subprocess.run(["sudo", "-n", "mn", "-c"], capture_output=True)
        log_b = open("/tmp/arena_bridge.log", "w")
        procs["bridge"] = subprocess.Popen(
            [sys.executable, "-m", "fl_ids.sdn.bridge", "--listen-port", "8080"], cwd=ROOT, stdout=log_b, stderr=subprocess.STDOUT)
        for _ in range(60):
            try:
                requests.get(BRIDGE + "/health", timeout=1).raise_for_status()
                break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            raise RuntimeError("bridge did not start (see /tmp/arena_bridge.log)")

        BOOT["message"] = "Building the network: 6 switches, 15 hosts"
        log_a = open("/tmp/arena_agent.log", "w")
        procs["agent"] = subprocess.Popen(
            ["sudo", "-n", "/usr/bin/python3", str(ROOT / "fl_ids" / "arena" / "netagent.py")], cwd=ROOT,
            stdout=log_a, stderr=subprocess.STDOUT)
        topo = None
        for _ in range(120):
            try:
                topo = requests.get(AGENT + "/topology", timeout=1).json()
                dps = requests.get(BRIDGE + "/health", timeout=1).json()["connected_datapaths"]
                if len(dps) >= len(topo["switches"]):
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("network did not come up (see /tmp/arena_agent.log)")
        dpid = {s["name"]: s["dpid"] for s in topo["switches"]}
        for h in topo["hosts"]:
            HOST[h["name"]].update(mac=h["mac"], switch=h["switch"], dpid=dpid[h["switch"]])
            requests.post(BRIDGE + "/devices/register", json={
                "device_id": h["name"], "datapath_id": dpid[h["switch"]], "ip_address": h["ip"],
                "port_name": h["switch_port"]}, timeout=5)

        BOOT["message"] = "Loading the trained models"
        from fl_ids.orchestration.artifacts import load_phase_a_artifacts
        from fl_ids.utils.config import load_config
        CTX["art"] = load_phase_a_artifacts(BUNDLE, load_config().boosting)
        CTX["benign"] = {k: np.load(ASSETS / f"benign_c{c}.npy") for k, c in BUNDLE_CLIENTS.items()}
        CTX["window"] = {c: count_packets(SLICES / f"{c}_w.pcap") for c in CLASSES}
        CTX["rng"] = np.random.default_rng()
        if not CTX.get("poller"):
            CTX["poller"] = True
            threading.Thread(target=poller, daemon=True).start()
        BOOT.update(state="ready", message="Ready")
        emit("boot", message="Network and models ready")
    except Exception as e:  # noqa: BLE001
        logger.exception("boot failed")
        BOOT.update(state="error", message=str(e))


def poller() -> None:
    last_switch = 0.0
    while True:
        try:
            c = requests.get(AGENT + "/counters", timeout=2).json()
            TX.update(c["tx"])
            SENDING.update(c["sending"])
        except requests.RequestException:
            pass
        if time.time() - last_switch > 1.0:
            last_switch = time.time()
            try:
                st = requests.get(BRIDGE + "/switch_state", timeout=3).json()
                for dp, body in st.items():
                    for fl in body.get("flows") or []:
                        ip = fl["match"].get("ipv4_src")
                        if ip and fl["priority"] >= 100:
                            hid = next((h["id"] for h in HOSTS if h["ip"] == ip and str(h.get("dpid")) == dp), None)
                            if hid:
                                key = hid
                                prev = SWITCH_DROPS.get(key, {}).get("packets", -1)
                                SWITCH_DROPS[key] = {"packets": fl["packet_count"], "actions": fl["actions"],
                                                     "priority": fl["priority"], "dpid": dp, "ip": ip,
                                                     "match": fl["match"]}
                                if fl["packet_count"] != prev:
                                    emit("dropped", host=hid, packets=fl["packet_count"], rule=fl["actions"])
            except requests.RequestException:
                pass
        time.sleep(0.3)


# ------------------------------------------------------------------ one host's run
def run_host(hid: str) -> None:
    global RUN_LAUNCHED
    h, role = HOST[hid], ROLES[hid]
    art, truth = CTX["art"], role
    t_launch = time.time()
    emit("launch", host=hid, role=role, client=h["client"])
    try:
        if role == "normal":
            rows = CTX["benign"][h["client"]]
            n = min(WINDOW_PACKETS, len(rows))
            for step in range(1, 7):
                time.sleep(0.5)
                emit("progress", host=hid, packets=int(n * step / 6), total=n, source="dataset")
            X = rows[CTX["rng"].choice(len(rows), size=n, replace=False)]
            source, extract_ms = "dataset", 0.0
        else:
            n = CTX["window"][role]
            base = TX.get(hid, 0)
            r = agent("POST", "/replay", host=hid, pcap=str(SLICES / f"{role}.pcap"), pps=PPS)
            if "error" in r:
                raise RuntimeError(r["error"])
            last = 0.0
            while TX.get(hid, 0) - base < n and time.time() - t_launch < 30:
                if time.time() - last > 0.4:
                    last = time.time()
                    emit("progress", host=hid, packets=max(0, TX.get(hid, 0) - base), total=n, source="wire")
                time.sleep(0.1)
            emit("progress", host=hid, packets=n, total=n, source="wire")
            emit("analysing", host=hid)
            from fl_ids.sdn.feature_extraction import extract_features_for_inference
            t1 = time.time()
            X = extract_features_for_inference(SLICES / f"{role}_w.pcap", art.feature_names)
            extract_ms, source = (time.time() - t1) * 1000, "wire"
        emit("analysing", host=hid) if role == "normal" else None
        t2 = time.time()
        with CLS_LOCK:
            v = window_verdict(art, h["bundle_client"], X)
        classify_ms = (time.time() - t2) * 1000
        is_attack_truth = truth != "normal"
        top = sorted(v.by_label.items(), key=lambda kv: -kv[1])[:5]
        emit("verdict", host=hid, truth=truth, label=v.label, is_attack=v.is_attack, confidence=round(v.confidence, 4),
             stage=v.stage, share=round(v.share_flagged, 4), packets=v.num_packets, flagged=v.num_flagged, top=top,
             detect_ok=(v.is_attack == is_attack_truth), type_ok=(v.label == truth) if is_attack_truth else (not v.is_attack),
             extract_ms=round(extract_ms, 1), classify_ms=round(classify_ms, 1), source=source)
        if v.is_attack:
            t3 = time.time()
            resp = requests.post(BRIDGE + "/mitigate", json={
                "device_id": hid, "classification": v.label, "confidence": float(v.confidence), "stage": v.stage},
                timeout=10).json()
            emit("mitigation", host=hid, action=resp.get("action"), applied=resp.get("applied"),
                 bridge_ms=round((time.time() - t3) * 1000, 1), time_to_action_s=round(time.time() - t_launch, 2))
        else:
            emit("mitigation", host=hid, action="allow", applied=True, bridge_ms=0, time_to_action_s=round(time.time() - t_launch, 2))
        if role != "normal":
            while SENDING.get(hid) and time.time() - t_launch < 60:
                time.sleep(0.3)
            time.sleep(1.3)
        emit("host_done", host=hid)
    except Exception as e:  # noqa: BLE001
        logger.exception("host run failed")
        emit("error", host=hid, message=str(e))
    finally:
        with LOCK:
            BUSY.discard(hid)
            finished = not BUSY
        if finished:
            emit("run_done")
            save_recording()


def save_recording() -> None:
    with LOCK:
        start = max((e["i"] for e in EVENTS if e["type"] == "reset"), default=-1) + 1
        start = max(start, CTX.get("saved_upto", 0))
        evs = EVENTS[start:]
        if any(e["type"] == "launch" for e in evs):
            CTX["saved_upto"] = len(EVENTS)
    if not any(e["type"] == "launch" for e in evs):
        return
    RECORDINGS.mkdir(exist_ok=True)
    roles_ = [e["role"] for e in evs if e["type"] == "launch"]
    n_norm = sum(r == "normal" for r in roles_)
    name = time.strftime("run-%Y%m%d-%H%M%S") + f"-{len(roles_) - n_norm}attack-{n_norm}normal.json"
    base = evs[0]["t"]
    (RECORDINGS / name).write_text(json.dumps(
        {"name": name, "roles": {e["host"]: e["role"] for e in evs if e["type"] == "launch"},
         "events": [{**e, "t": round(e["t"] - base, 3)} for e in evs]}))


# ------------------------------------------------------------------ API
@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:p>")
def static_files(p):
    return send_from_directory(STATIC, p)


@app.get("/api/config")
def config():
    return jsonify({"hosts": [{k: h[k] for k in ("id", "client", "ip")} for h in HOSTS], "classes": CLASSES,
                    "window": WINDOW_PACKETS, "pps": PPS, "share_threshold": SHARE_THRESHOLD,
                    "roles": ROLES, "boot": BOOT})


@app.post("/api/boot")
def boot():
    if BOOT["state"] in ("off", "error"):
        BOOT.update(state="starting", message="Starting")
        threading.Thread(target=boot_worker, daemon=True).start()
    return jsonify(BOOT)


@app.get("/api/boot")
def boot_status():
    return jsonify(BOOT)


@app.post("/api/role")
def set_role():
    b = request.get_json(force=True)
    hid, role = b["host"], b["role"]
    if hid in BUSY or hid not in HOST or role not in ["idle", "normal"] + CLASSES:
        return jsonify({"error": "cannot change this host now"}), 400
    ROLES[hid] = role
    emit("role", host=hid, role=role)
    return jsonify({"ok": True})


@app.post("/api/launch")
def launch():
    if BOOT["state"] != "ready":
        return jsonify({"error": "network not ready"}), 400
    ids = request.get_json(force=True).get("hosts", "all")
    ids = [h["id"] for h in HOSTS] if ids == "all" else ids
    started = []
    for hid in ids:
        if ROLES.get(hid, "idle") == "idle":
            continue
        with LOCK:
            if hid in BUSY:
                continue
            BUSY.add(hid)
        started.append(hid)
    for hid in started:
        threading.Thread(target=run_host, args=(hid,), daemon=True).start()
    return jsonify({"started": started})


@app.post("/api/reset")
def reset():
    save_recording()
    try:
        agent("POST", "/stop")
    except requests.RequestException:
        pass
    for hid in list(SWITCH_DROPS):
        try:
            requests.post(BRIDGE + "/mitigate", json={"device_id": hid, "classification": "benign", "confidence": 1.0}, timeout=5)
        except requests.RequestException:
            pass
    SWITCH_DROPS.clear()
    BUSY.clear()
    for hid in ROLES:
        ROLES[hid] = "idle"
    emit("reset")
    return jsonify({"ok": True})


@app.get("/api/events")
def events():
    since = int(request.args.get("since", 0))
    with LOCK:
        return jsonify({"events": EVENTS[since:], "next": len(EVENTS), "boot": BOOT, "busy": sorted(BUSY)})


@app.get("/api/switch")
def switch():
    return jsonify(SWITCH_DROPS)


@app.get("/api/recordings")
def recordings():
    RECORDINGS.mkdir(exist_ok=True)
    return jsonify(sorted((p.name for p in RECORDINGS.glob("run-*.json")), reverse=True))


@app.get("/api/recordings/<name>")
def recording(name):
    return send_from_directory(RECORDINGS, name)


@app.get("/api/benchmark")
def benchmark():
    p = ASSETS / "window_benchmark.json"
    return send_from_directory(ASSETS, "window_benchmark.json") if p.exists() else jsonify({})


def cleanup() -> None:
    try:
        agent("POST", "/shutdown")
    except requests.RequestException:
        pass
    for name in ("bridge", "agent"):
        p = procs.pop(name, None)
        if p and p.poll() is None:
            p.terminate()
    subprocess.run(["sudo", "-n", "mn", "-c"], capture_output=True)
    HOSTS_RESET()
    BOOT.update(state="off", message="Network stopped")


def HOSTS_RESET() -> None:
    BUSY.clear()
    SWITCH_DROPS.clear()
    for hid in ROLES:
        ROLES[hid] = "idle"


@app.post("/api/shutdown")
def shutdown():
    save_recording()
    cleanup()
    emit("reset")
    return jsonify({"ok": True})


if __name__ == "__main__":
    import atexit
    import signal

    logging.basicConfig(level=logging.INFO)
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    app.run(host="127.0.0.1", port=8090, threaded=True)
