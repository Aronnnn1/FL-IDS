"""One-off: rebuild Phase A's per-client held-out test slices (same code and seed as the full c10_s42 run),
save normal rows for the arena's normal hosts, and measure the host-window rule on held-out dataset windows.

Run in the VM:  venv/bin/python -m fl_ids.arena.prepare_assets
"""

import json, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fl_ids.data.pipeline import (calibration_eval_split, load_and_encode, partition_and_normalize_clients,
                                  server_pool_split, load_flow_ids)
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.utils.config import load_config
from fl_ids.arena.verdict import window_verdict, WINDOW_PACKETS

OUT = ROOT / "arena_assets"
OUT.mkdir(exist_ok=True)
CLIENTS = list(range(10))
THRESHOLDS = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]

t0 = time.time()
cfg = load_config(ROOT / "configs" / "full" / "c10_s42.yaml")
X, y, le, feature_names, benign = load_and_encode(cfg.data.dnn_csv_path, cfg.data.capture_repairs,
                                                  cfg.data.extended_features, cfg.data.feature_cache)
class_names = list(le.classes_)
X_calib, y_calib, X_pool, y_pool, g_calib, g_pool = server_pool_split(X, y, cfg, cfg.seed, cfg.orchestration.pool_subsample_size)
client_data = partition_and_normalize_clients(X_pool, y_pool, benign, cfg.data, cfg.seed, groups=g_pool)
print("split rebuilt in %.0fs" % (time.time() - t0), {k: len(v["y_test"]) for k, v in client_data.items()})

art = load_phase_a_artifacts(ROOT / "saved_models" / "full" / "c10_s42", cfg.boosting)
rng = np.random.default_rng(7)
bench = {"window_packets": WINDOW_PACKETS, "clients": {}}
for c in CLIENTS:
    cd = client_data[c]
    Xt, yt = cd["X_test_raw"], cd["y_test"]
    ben = Xt[yt == benign]
    np.save(OUT / f"benign_c{c}.npy", ben[:40000].astype(np.float32))
    rec = {"benign_test_rows": int(len(ben)), "benign": {}, "attacks": {}}
    # benign windows
    shares = []
    for _ in range(200):
        n = min(WINDOW_PACKETS, len(ben))
        if n == 0:
            break
        idx = rng.choice(len(ben), size=n, replace=False)
        v = window_verdict(art, c, ben[idx], share_threshold=1.01)
        shares.append(v.share_flagged)
    rec["benign"]["shares_pctiles"] = {p: float(np.percentile(shares, p)) for p in (5, 50, 95, 99, 100)} if shares else {}
    rec["benign"]["false_block_rate_by_threshold"] = {str(t): float(np.mean(np.array(shares) >= t)) for t in THRESHOLDS} if shares else {}
    # attack windows from held-out dataset rows
    for ci, name in enumerate(class_names):
        if ci == benign:
            continue
        att = Xt[yt == ci]
        if len(att) < 300:
            continue
        res = []
        for _ in range(20):
            n = min(WINDOW_PACKETS, len(att))
            idx = rng.choice(len(att), size=n, replace=False)
            v = window_verdict(art, c, att[idx], share_threshold=0.0)
            res.append((v.share_flagged, v.label))
        sh = np.array([r[0] for r in res])
        rec["attacks"][name] = {
            "rows": int(len(att)),
            "detect_rate_by_threshold": {str(t): float(np.mean(sh >= t)) for t in THRESHOLDS},
            "type_correct_rate": float(np.mean([r[1] == name for r in res])),
        }
    bench["clients"][str(c)] = rec
    print("client", c, "benign rows", len(ben), json.dumps(rec["benign"]))
(OUT / "window_benchmark.json").write_text(json.dumps(bench, indent=1))
print("done in %.0fs" % (time.time() - t0))
