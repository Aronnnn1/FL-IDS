"""Precompute the arena's real verdicts for every (client network, role) pair, for the hosted simulation page.

Each entry is the cascade's actual output for that client's model on the real capture window (features extracted with
TShark from the same slice the live arena replays), or on a random draw of the client's real held-out normal rows.
Run in the VM:  venv/bin/python -m fl_ids.arena.verdict_table
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fl_ids.arena.server import BUNDLE, BUNDLE_CLIENTS, CLASSES, SLICES, ASSETS, count_packets  # noqa: E402
from fl_ids.arena.verdict import WINDOW_PACKETS, window_verdict  # noqa: E402
from fl_ids.orchestration.artifacts import load_phase_a_artifacts  # noqa: E402
from fl_ids.sdn.bridge import classify_mitigation_action  # noqa: E402
from fl_ids.sdn.feature_extraction import extract_features_for_inference  # noqa: E402
from fl_ids.utils.config import load_config  # noqa: E402

cfg = load_config()
art = load_phase_a_artifacts(BUNDLE, cfg.boosting)
bench = json.loads((ASSETS / "window_benchmark.json").read_text())
rng = np.random.default_rng(11)


def entry(v, extract_ms, classify_ms):
    action = classify_mitigation_action(v.label, v.confidence, cfg.sdn) if v.is_attack else "allow"
    return {"label": v.label, "is_attack": v.is_attack, "confidence": round(v.confidence, 4), "stage": v.stage,
            "share": round(v.share_flagged, 4), "packets": v.num_packets, "flagged": v.num_flagged,
            "top": sorted(v.by_label.items(), key=lambda kv: -kv[1])[:5], "extract_ms": round(extract_ms, 1),
            "classify_ms": round(classify_ms, 1), "action": action}


feats = {}
for c in CLASSES:
    t = time.time()
    feats[c] = (extract_features_for_inference(SLICES / f"{c}_w.pcap", art.feature_names), (time.time() - t) * 1000)

out = {"window": {c: count_packets(SLICES / f"{c}_w.pcap") for c in CLASSES},
       "slice": {c: count_packets(SLICES / f"{c}.pcap") for c in CLASSES}, "share_threshold": 0.25, "clients": {}}
for k, bc in BUNDLE_CLIENTS.items():
    b = bench["clients"][str(bc)]
    rec = {"bundle_client": bc, "benign_rows": b["benign_test_rows"],
           "benign_share_median": (b["benign"].get("shares_pctiles") or {}).get("50"), "classes": {}, "normal": []}
    for c in CLASSES:
        X, ems = feats[c]
        t = time.time()
        v = window_verdict(art, bc, X)
        rec["classes"][c] = entry(v, ems, (time.time() - t) * 1000)
    ben = np.load(ASSETS / f"benign_c{bc}.npy")
    for _ in range(6):
        n = min(WINDOW_PACKETS, len(ben))
        X = ben[rng.choice(len(ben), size=n, replace=False)]
        t = time.time()
        v = window_verdict(art, bc, X)
        rec["normal"].append(entry(v, 0.0, (time.time() - t) * 1000))
    out["clients"][str(k)] = rec
    print("net", k, "client", bc, {c: rec["classes"][c]["label"] + "/" + rec["classes"][c]["action"] for c in ("MITM", "Fingerprinting", "XSS")},
          "normal flagged", [e["share"] for e in rec["normal"]])
(ASSETS / "verdict_table.json").write_text(json.dumps(out))
print("saved")
