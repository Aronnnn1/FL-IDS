"""Per-class and per-client breakdown of a saved Phase A bundle on its clients' held-out test slices.

Phase A's own log line gives one attack macro-recall. This reloads the saved bundle and the run's per-client data
files and shows where that number comes from: recall per attack class for each cascade stage, and recall per client
(including which clients had no benign validation rows and therefore an infinite autoencoder threshold).

    python -m fl_ids.eval.bundle_report --config-path configs/config_20clients_real.yaml \
        --artifact-dir saved_models/phase_a_20c_real --run-dir runs/clients20_real/phase_a \
        --output-dir results/real_runs/c20_s42
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from fl_ids.eval.common import concat_client_test_slices, per_row_thresholds
from fl_ids.eval.metrics import detection_metrics, flag_attacks
from fl_ids.fl.data_io import load_client_data
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.utils.config import load_config

logger = logging.getLogger(__name__)
MODES = ("boosting_only", "autoencoder_only", "cascade")


def load_run_clients(run_dir: Path) -> dict[int, dict[str, np.ndarray]]:
    """Every `client_<id>.npz` Phase A wrote to its run directory."""
    return {int(p.stem.split("_")[1]): load_client_data(p) for p in sorted(run_dir.glob("client_*.npz"))}


def bundle_report(config_path: str, artifact_dir: str, run_dir: str, output_dir: str) -> dict:
    """Write per-class and per-client detection tables for one bundle; return the summary dict."""
    config = load_config(config_path)
    art = load_phase_a_artifacts(artifact_dir, config.boosting)
    client_data = load_run_clients(Path(run_dir))
    X_raw, X_norm, y, client_ids = concat_client_test_slices(client_data)
    thresholds = per_row_thresholds(art.client_thresholds, client_ids)
    flags = {
        m: flag_attacks(m, art.boosting_model, art.autoencoder, thresholds, X_raw, X_norm, art.class_names, art.cascade_config)
        for m in MODES
    }
    metrics = {m: detection_metrics(flags[m], y, art.benign_class, art.class_names) for m in MODES}

    classes = sorted({art.class_names[c] for c in np.unique(y) if c != art.benign_class})
    per_class = pd.DataFrame(
        [
            {"class": c, "test_rows": int((y == art.class_names.index(c)).sum()),
             **{m: metrics[m]["per_class_recall"][c] for m in MODES}}
            for c in classes
        ]
    )
    rows = []
    for cid in sorted(client_data):
        sel = client_ids == cid
        attack = sel & (y != art.benign_class)
        benign = sel & (y == art.benign_class)
        rows.append(
            {
                "client": cid,
                "test_rows": int(sel.sum()),
                "attack_rows": int(attack.sum()),
                "benign_rows": int(benign.sum()),
                "benign_val_rows": int(len(client_data[cid]["X_val_benign"])),
                "threshold_infinite": bool(not np.isfinite(art.client_thresholds[cid])),
                "cascade_attack_recall": float(flags["cascade"][attack].mean()) if attack.any() else float("nan"),
                "boosting_attack_recall": float(flags["boosting_only"][attack].mean()) if attack.any() else float("nan"),
                "cascade_fpr": float(flags["cascade"][benign].mean()) if benign.any() else float("nan"),
            }
        )
    per_client = pd.DataFrame(rows)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    per_class.to_csv(out / "per_class_recall.csv", index=False)
    per_client.to_csv(out / "per_client.csv", index=False)
    summary = {m: {k: v for k, v in metrics[m].items() if k != "per_class_recall"} for m in MODES}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return {"summary": summary, "per_class": per_class, "per_client": per_client}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    result = bundle_report(args.config_path, args.artifact_dir, args.run_dir, args.output_dir)
    print(json.dumps(result["summary"], indent=2))
    print(result["per_class"].to_string(index=False))
    print(result["per_client"].to_string(index=False))


if __name__ == "__main__":
    main()
