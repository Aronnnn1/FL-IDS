"""Root-side half of the live arena: builds the Mininet network and replays real captures on command.

Topology: one core switch (s1) and five client switches (s2..s6). Client k (1..5) has three hosts
c<k>h1..c<k>h3 (10.0.<k>.1..3/16) on switch s<k+1>. All switches use the project's OpenFlow controller.

Control API (127.0.0.1 only, JSON):  GET /topology  GET /counters  POST /replay  POST /stop  POST /shutdown
Run (as root):  sudo /usr/bin/python3 fl_ids/arena/netagent.py
"""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "venv" / "lib" / "python3.14" / "site-packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

CLIENTS, HOSTS_PER_CLIENT = 5, 3
PORT = 8099
PCAP_ALLOWED_DIR = ROOT / "arena_assets" / "slices"

net: Mininet | None = None
procs: dict[str, subprocess.Popen] = {}
lock = threading.Lock()


def build() -> Mininet:
    n = Mininet(switch=OVSSwitch, controller=None, autoSetMacs=True)
    n.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    core = n.addSwitch("s1", protocols="OpenFlow13")
    for k in range(1, CLIENTS + 1):
        access = n.addSwitch(f"s{k + 1}", protocols="OpenFlow13")
        n.addLink(access, core)
        for j in range(1, HOSTS_PER_CLIENT + 1):
            h = n.addHost(f"c{k}h{j}", ip=f"10.0.{k}.{j}/16")
            n.addLink(h, access)
    n.start()
    return n


def topology() -> dict:
    hosts = []
    for h in net.hosts:
        intf = h.defaultIntf()
        link = intf.link
        sw_intf = link.intf2 if link.intf1.node is h else link.intf1
        hosts.append({"name": h.name, "ip": h.IP(), "mac": h.MAC(), "iface": intf.name,
                      "switch": sw_intf.node.name, "switch_port": sw_intf.name})
    switches = [{"name": s.name, "dpid": int(s.dpid, 16)} for s in net.switches]
    return {"hosts": hosts, "switches": switches}


def tx_counters() -> dict:
    out = {}
    for h in net.hosts:
        v = h.cmd(f"cat /sys/class/net/{h.defaultIntf().name}/statistics/tx_packets").strip()
        out[h.name] = int(v) if v.isdigit() else 0
    return out


def replay(host_name: str, pcap: str, pps: int) -> dict:
    src = Path(pcap).resolve()
    if PCAP_ALLOWED_DIR not in src.parents or src.suffix != ".pcap":
        return {"error": "pcap not allowed"}
    h = net.get(host_name)
    out = f"/tmp/arena_{host_name}.pcap"
    # every packet of the capture is sent from this host: map all source IPs to the host's IP,
    # so the controller's per-IP drop rule matches the replayed traffic
    rc = subprocess.run(
        ["tcprewrite", f"--infile={src}", f"--outfile={out}", f"--srcipmap=0.0.0.0/0:{h.IP()}",
         "--dstipmap=0.0.0.0/0:10.0.200.1", "--fixcsum"],
        capture_output=True, text=True)
    if rc.returncode != 0:
        return {"error": rc.stderr[-300:]}
    with lock:
        old = procs.pop(host_name, None)
        if old and old.poll() is None:
            old.terminate()
        procs[host_name] = h.popen(
            ["tcpreplay", f"--intf1={h.defaultIntf().name}", f"--pps={pps}", out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"started": host_name}


def stop(host_name: str | None) -> None:
    with lock:
        names = [host_name] if host_name else list(procs)
        for nme in names:
            p = procs.pop(nme, None)
            if p and p.poll() is None:
                p.terminate()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/topology":
            self._send(topology())
        elif self.path == "/counters":
            with lock:
                alive = {k: (v.poll() is None) for k, v in procs.items()}
            self._send({"tx": tx_counters(), "sending": alive})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/replay":
            self._send(replay(body["host"], body["pcap"], int(body.get("pps", 1000))))
        elif self.path == "/stop":
            stop(body.get("host"))
            self._send({"stopped": True})
        elif self.path == "/shutdown":
            self._send({"bye": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    setLogLevel("warning")
    net = build()
    print("netagent: network up", flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        srv.serve_forever()
    finally:
        stop(None)
        net.stop()
