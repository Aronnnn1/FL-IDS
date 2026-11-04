"""How much of each arena attack window was seen when the classifier was trained?

Same split code and seed as the full c10_s42 run. For every attack capture, take the 3,000-packet window the arena
classifies, match its rows to the dataset rows (by the 130 feature values), and report how many rows sit in the
server's calibration set (the only labelled attack data the classifier trained on, plus ~2k alert rows).

Run in the VM:  venv/bin/python -m fl_ids.arena.overlap_check
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fl_ids.data.pipeline import load_and_encode, server_pool_split
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.sdn.feature_extraction import extract_features_for_inference
from fl_ids.utils.config import load_config

cfg = load_config(ROOT / "configs" / "full" / "c10_s42.yaml")
X, y, le, feature_names, benign = load_and_encode(cfg.data.dnn_csv_path, cfg.data.capture_repairs,
                                                  cfg.data.extended_features, cfg.data.feature_cache)
names = list(le.classes_)
X_calib, y_calib, X_pool, y_pool, g_calib, g_pool = server_pool_split(X, y, cfg, cfg.seed, cfg.orchestration.pool_subsample_size)


def h(M):
    return pd.util.hash_pandas_object(pd.DataFrame(np.round(np.asarray(M, dtype=np.float64), 5)), index=False).values


calib_hashes = set(h(X_calib).tolist())
pool_hashes = set(h(X_pool).tolist())
art = load_phase_a_artifacts(ROOT / "saved_models" / "full" / "c10_s42", cfg.boosting)
out = {}
for cls in names:
    if cls in ("Normal",):
        continue
    p = ROOT / "arena_assets" / "slices" / f"{cls}_w.pcap"
    if not p.exists():
        continue
    W = extract_features_for_inference(p, art.feature_names)
    hw = h(W).tolist()
    in_c = sum(1 for v in hw if v in calib_hashes)
    in_p = sum(1 for v in hw if v in pool_hashes)
    out[cls] = {"window_rows": len(hw), "in_calibration": in_c, "in_client_pool": in_p, "unmatched": len(hw) - in_c - in_p}
    print(f"{cls:22s} rows={len(hw):5d} calibration={in_c:5d} ({100*in_c/len(hw):5.1f}%) client_pool={in_p:5d} unmatched={len(hw)-in_c-in_p}", flush=True)
(ROOT / "arena_assets" / "overlap_check.json").write_text(json.dumps(out, indent=1))
