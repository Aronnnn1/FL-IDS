"""Single-feature AUROC before and after the placeholder fix -> results/leak/single_feature_auroc.json (for a figure).

Before: the four affected raw columns, scored as "is the value spelled 0.0" (attack vs. normal). After: the best single
features of the current 130-feature matrix (placeholders canonicalised), on a stratified 300k-row sample.
Run from the repo root:  venv/bin/python tools/leak_auroc.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
COLS = ["mqtt.topic", "mqtt.conack.flags", "mqtt.protoname", "dns.qry.name.len"]
raw = pd.read_csv(ROOT / "data/raw/DNN-EdgeIIoT-dataset.csv", usecols=COLS + ["Attack_label"], dtype=str, low_memory=False)
y = raw["Attack_label"].astype(float).astype(int).to_numpy()
before = {}
for c in COLS:
    score = (raw[c].astype(str).str.strip() == "0.0").astype(float).to_numpy()
    before[c + " == 0.0"] = float(max(roc_auc_score(y, score), 1 - roc_auc_score(y, score)))

npz = np.load(ROOT / "data/processed/encoded_extended.npz", allow_pickle=True)
print(npz.files)
X, labels = npz["X"], npz["y"]
names = npz["feature_names"]
normal = int(npz["benign_class"])
rng = np.random.default_rng(0)
idx = rng.choice(len(X), size=min(300_000, len(X)), replace=False)
yy = (labels[idx] != normal).astype(int)
aucs = {}
for j in range(X.shape[1]):
    col = X[idx, j].astype(np.float64)
    if np.ptp(col) == 0:
        continue
    a = roc_auc_score(yy, col)
    aucs[str(names[j])] = float(max(a, 1 - a))
top = dict(sorted(aucs.items(), key=lambda kv: -kv[1])[:6])
out = ROOT / "results" / "leak"
out.mkdir(parents=True, exist_ok=True)
(out / "single_feature_auroc.json").write_text(json.dumps({"before": before, "after": top, "sample_rows": int(len(idx))}, indent=2))
print(json.dumps({"before": before, "after": top}, indent=2))
