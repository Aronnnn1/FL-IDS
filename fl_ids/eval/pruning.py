"""Weight-pruning study for the federated autoencoder (project Objective 3).

Magnitude-prunes the trained global autoencoder after training (global threshold over all weight matrices, biases kept),
re-calibrates every client's anomaly threshold on its own benign validation rows with the pruned model (as a deployed
pruned model would be), and scores the cascade and the autoencoder alone on the clients' held-out test slices.

This is post-training pruning of the final model. It does not prune during federated training and it does not measure
sparse updates on the wire; the size columns are computed from the non-zero counts (float32 values plus int32 indices
for a sparse layout), so they are the size a sparse encoding would have, not a transmitted size.

    python -m fl_ids.eval.pruning --config-path configs/config_vmware_check.yaml \
        --artifact-dir saved_models/vmware_check_phase_a --run-dir runs/vmware_check/phase_a --output-dir results/pruning
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from fl_ids.eval.bundle_report import load_run_clients
from fl_ids.eval.common import concat_client_test_slices, per_row_thresholds
from fl_ids.eval.metrics import detection_metrics, flag_attacks
from fl_ids.models.autoencoder import compute_anomaly_threshold, reconstruction_error
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.utils.config import load_config

logger = logging.getLogger(__name__)
SPARSITIES = (0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.98)


def prune_global_magnitude(autoencoder, sparsity: float):
    """Copy of `autoencoder` with the smallest `sparsity` fraction of weight-matrix entries (by |w|) set to zero."""
    pruned = copy.deepcopy(autoencoder)
    weights = [p for name, p in pruned.named_parameters() if p.dim() > 1]
    if sparsity > 0:
        magnitudes = np.concatenate([p.detach().abs().flatten().numpy() for p in weights])
        cutoff = np.quantile(magnitudes, sparsity)
        for p in weights:
            p.data[p.detach().abs() <= cutoff] = 0.0
    return pruned


def sizes(autoencoder) -> dict:
    """Parameter counts and byte sizes: dense float32, and a sparse layout (values + int32 indices) for the weight matrices."""
    dense_params = sum(p.numel() for p in autoencoder.parameters())
    matrix_nnz = sum(int((p != 0).sum()) for p in autoencoder.parameters() if p.dim() > 1)
    bias_params = sum(p.numel() for p in autoencoder.parameters() if p.dim() == 1)
    sparse_bytes = matrix_nnz * 8 + bias_params * 4
    return {"parameters": dense_params, "nonzero_weights": matrix_nnz, "dense_bytes": dense_params * 4, "sparse_bytes": sparse_bytes}


def run(config_path: str, artifact_dir: str, run_dir: str, output_dir: str) -> pd.DataFrame:
    config = load_config(config_path)
    art = load_phase_a_artifacts(artifact_dir, config.boosting)
    clients = load_run_clients(Path(run_dir))
    X_raw, X_norm, y, client_ids = concat_client_test_slices(clients)
    is_attack = y != art.benign_class
    percentile = config.autoencoder.anomaly_percentile
    rows = []
    for sparsity in SPARSITIES:
        model = prune_global_magnitude(art.autoencoder, sparsity)
        thresholds = {
            cid: compute_anomaly_threshold(reconstruction_error(model, d["X_val_benign"]), percentile)
            if len(d["X_val_benign"]) else float("inf")
            for cid, d in clients.items()
        }
        row_thr = per_row_thresholds(thresholds, client_ids)
        casc = detection_metrics(
            flag_attacks("cascade", art.boosting_model, model, row_thr, X_raw, X_norm, art.class_names, art.cascade_config),
            y, art.benign_class, art.class_names)
        ae = detection_metrics(
            flag_attacks("autoencoder_only", None, model, row_thr, X_raw, X_norm, art.class_names, art.cascade_config),
            y, art.benign_class, art.class_names)
        auroc = float(roc_auc_score(is_attack, reconstruction_error(model, X_norm)))
        s = sizes(model)
        rows.append({
            "sparsity": sparsity, **s,
            "sparse_vs_dense_bytes": s["sparse_bytes"] / s["dense_bytes"],
            "ae_attack_macro_recall": ae["attack_macro_recall"], "ae_auroc": auroc,
            "cascade_attack_macro_recall": casc["attack_macro_recall"], "cascade_attack_micro_recall": casc["attack_micro_recall"],
            "benign_fpr": casc["benign_fpr"],
        })
        logger.info("sparsity=%.2f nnz=%d ae_recall=%.3f auroc=%.3f cascade_macro=%.3f fpr=%.4f", sparsity, s["nonzero_weights"],
                    ae["attack_macro_recall"], auroc, casc["attack_macro_recall"], casc["benign_fpr"])
    df = pd.DataFrame(rows)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "pruning.csv", index=False)
    (out / "meta.json").write_text(json.dumps({"artifact_dir": artifact_dir, "run_dir": run_dir, "method": "global magnitude, post-training, thresholds recalibrated"}, indent=2))
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", default="results/pruning")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(run(args.config_path, args.artifact_dir, args.run_dir, args.output_dir).to_string(index=False))


if __name__ == "__main__":
    main()
