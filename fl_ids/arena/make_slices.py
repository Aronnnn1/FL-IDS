"""Cut the first packets of each real attack capture into small .pcap slices for the live arena.

For every attack class: <Class>.pcap  = first SLICE_PACKETS packets (what an attacker host replays on the wire)
                        <Class>_w.pcap = first WINDOW_PACKETS packets (the window the cascade classifies)
Run in the VM:  venv/bin/python -m fl_ids.arena.make_slices
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fl_ids.arena.verdict import WINDOW_PACKETS

SLICE_PACKETS = 12000
PCAPS = ROOT / "data" / "raw" / "pcaps"
OUT = ROOT / "arena_assets" / "slices"

CAPTURES = {
    "Backdoor": "Backdoor_attack.pcap",
    "DDoS_HTTP": "DDoS HTTP Flood Attacks.pcap",
    "DDoS_ICMP": "DDoS ICMP Flood Attacks.pcap",
    "DDoS_TCP": "DDoS TCP SYN Flood Attacks.pcap",
    "DDoS_UDP": "DDoS UDP Flood Attacks.pcap",
    "Fingerprinting": "OS Fingerprinting attack.pcap",
    "MITM": "MITM (ARP spoofing + DNS) Attack.pcap",
    "Password": "Password attacks.pcap",
    "Port_Scanning": "Port Scanning attack.pcap",
    "Ransomware": "Ransomware attack.pcap",
    "SQL_injection": "SQL injection attack.pcap",
    "Uploading": "Uploading attack.pcap",
    "Vulnerability_scanner": "Vulnerability scanner attack.pcap",
    "XSS": "XSS attacks.pcap",
}


def write_prefix(src: Path, dst: Path, n: int) -> int:
    with open(src, "rb") as f, open(dst, "wb") as o:
        gh = f.read(24)
        endian = "<" if gh[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        o.write(gh)
        k = 0
        while k < n:
            h = f.read(16)
            if len(h) < 16:
                break
            incl = struct.unpack(endian + "IIII", h)[2]
            o.write(h)
            o.write(f.read(incl))
            k += 1
    return k


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for cls, name in CAPTURES.items():
        n_slice = write_prefix(PCAPS / name, OUT / f"{cls}.pcap", SLICE_PACKETS)
        n_win = write_prefix(PCAPS / name, OUT / f"{cls}_w.pcap", WINDOW_PACKETS)
        print(f"{cls:22s} slice={n_slice:6d} window={n_win:5d}")
