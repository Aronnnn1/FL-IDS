"""Boosting vs. supervised DL classifier -- component 2 alternative comparison.

Answers a different question from the `autoencoder_only` ablation variant
(`fl_ids.eval.variants`): not "is an unsupervised anomaly detector a viable
substitute for a classifier", but "of two *supervised* classifiers trained
on the same attack-type labels, which is more accurate" -- LightGBM
boosting (`fl_ids.models.boosting`, this project's chosen first-pass
classifier) against a dense feedforward net (`fl_ids.models.dl_classifier`).
See that module's docstring for why the comparison uses raw features for
boosting and standardized features for the DL classifier.

Runs on a **class-imbalance-capped sample** of the full dataset
(`fl_ids.data.sampling.capped_stratified_sample_indices`, default 500,000
rows -- see `ClassifierComparisonConfig`), not the full ~1.9M-row cleaned
dataset, and is a standalone, centralized (non-federated) comparison: no
FL rounds, no cascade, no per-client partitioning. That machinery answers
different questions (component 12's ablation); this script isolates the
classifier choice on its own.

    python -m fl_ids.eval.classifier_comparison
    python -m fl_ids.eval.classifier_comparison --sample-size 200000

Writes `results/classifier_comparison_summary.json` (headline numbers,
full-dataset vs. sampled per-class counts),
`results/classifier_comparison_per_class.csv` (both models' full per-class
table, `fl_ids.eval.metrics.build_per_stage_table`'s format), and
`results/classifier_comparison_confusion_matrices.json` (both models'
raw prediction grids on the same test rows -- `evaluate_boosting_alone`/
`evaluate_dl_classifier_alone` report precision/recall/F1/AUROC, not this).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from fl_ids.data.pipeline import load_and_encode
from fl_ids.data.sampling import capped_stratified_sample_indices, per_class_counts
from fl_ids.eval.metrics import build_per_stage_table, evaluate_boosting_alone, evaluate_dl_classifier_alone
from fl_ids.models.boosting import BoostingClassifier
from fl_ids.models.dl_classifier import DLClassifier, count_parameters, predict_proba, train_dl_classifier
from fl_ids.utils.config import Config, load_config
from fl_ids.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# The pcap-based MITM repair (fl_ids.data.repair) needs tshark and the raw
# .pcap capture, neither pulled down for this comparison (see PAPER_NOTES.md
# sect. 5.3.2 for what it fixes) -- explicitly skipped here rather than
# silently inherited from config.data.capture_repairs, and called out in the
# written summary so MITM's per-class numbers are read with that caveat.
CAPTURE_REPAIRS_SKIPPED_NOTE = (
    "This run used DNN-EdgeIIoT-dataset.csv's MITM rows without the pcap-based "
    "repair (fl_ids.data.repair skipped -- needs tshark + the raw .pcap, not "
    "pulled for this comparison). MITM's own per-class numbers should be read "
    "with that caveat (see PAPER_NOTES.md sect. 5.3.2); it's a tiny class "
    "either way (~0.02% of the cleaned dataset)."
)


def run_comparison(config: Config, csv_path: str, seed: int) -> tuple[dict, pd.DataFrame, dict]:
    """Load, sample, train both classifiers, and evaluate them on the same held-out split.

    Args:
        config: Full project config (`classifier_comparison`, `dl_classifier`,
            `boosting`, `cascade` sections).
        csv_path: Path to `DNN-EdgeIIoT-dataset.csv`.
        seed: Random seed, for reproducible sampling/splitting/training.

    Returns:
        (summary dict, per-class comparison DataFrame, confusion matrices dict).
    """
    logger.info("Loading and encoding %s", csv_path)
    X, y, label_encoder, _feature_names, benign_class = load_and_encode(csv_path, capture_repairs=None)
    class_names = list(label_encoder.classes_)
    full_counts = per_class_counts(y, class_names)
    logger.info("Full cleaned dataset: %d rows, %d classes", len(y), len(class_names))

    sample_idx = capped_stratified_sample_indices(y, config.classifier_comparison.sample_size, seed)
    X_sample, y_sample = X[sample_idx], y[sample_idx]
    sample_counts = per_class_counts(y_sample, class_names)

    X_train, X_test, y_train, y_test = train_test_split(
        X_sample,
        y_sample,
        test_size=config.classifier_comparison.test_fraction,
        random_state=seed,
        stratify=y_sample,
    )

    # Boosting always sees raw features (fl_ids.models.boosting); the DL
    # classifier sees the same rows standardized on the training split only
    # (fl_ids.models.dl_classifier's module docstring explains why).
    scaler = StandardScaler().fit(X_train)
    X_train_std = scaler.transform(X_train).astype(np.float32)
    X_test_std = scaler.transform(X_test).astype(np.float32)

    boosting_model = BoostingClassifier(
        config.boosting,
        num_classes=len(class_names),
        benign_class=benign_class,
        seed=seed,
        confidence_threshold=config.cascade.confidence_threshold,
    )
    t0 = time.perf_counter()
    boosting_model.train(X_train, y_train)
    boosting_train_seconds = time.perf_counter() - t0
    boosting_report = evaluate_boosting_alone(boosting_model, X_test, y_test, class_names, benign_class)

    dl_model = DLClassifier(
        input_dim=X.shape[1],
        hidden_dims=config.dl_classifier.hidden_dims,
        num_classes=len(class_names),
        dropout=config.dl_classifier.dropout,
    )
    t0 = time.perf_counter()
    epoch_losses = train_dl_classifier(dl_model, X_train_std, y_train, config.dl_classifier, seed)
    dl_train_seconds = time.perf_counter() - t0
    dl_report = evaluate_dl_classifier_alone(dl_model, X_test_std, y_test, class_names, benign_class)

    comparison_table = build_per_stage_table([boosting_report, dl_report])

    # Confusion matrices: not produced by evaluate_boosting_alone/
    # evaluate_dl_classifier_alone (they report precision/recall/F1/AUROC,
    # not the raw prediction grid), so computed directly here from each
    # model's own predictions on the same test rows.
    y_pred_boosting = np.argmax(boosting_model.predict_proba(X_test), axis=1)
    y_pred_dl = np.argmax(predict_proba(dl_model, X_test_std), axis=1)
    labels = list(range(len(class_names)))
    confusion_matrices = {
        "class_names": class_names,
        "boosting": confusion_matrix(y_test, y_pred_boosting, labels=labels).tolist(),
        "dl_classifier": confusion_matrix(y_test, y_pred_dl, labels=labels).tolist(),
    }

    summary = {
        "seed": seed,
        "sample_size_target": config.classifier_comparison.sample_size,
        "sample_size_actual": int(len(sample_idx)),
        "full_dataset_rows": int(len(y)),
        "full_dataset_class_counts": full_counts,
        "sample_class_counts": sample_counts,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "boosting": {
            "accuracy": boosting_report.accuracy,
            "macro_f1": boosting_report.macro_f1,
            "weighted_f1": boosting_report.weighted_f1,
            "benign_fpr": boosting_report.false_positive_rate,
            "train_seconds": boosting_train_seconds,
            "model_size_bytes": len(boosting_model.to_bytes()),
        },
        "dl_classifier": {
            "accuracy": dl_report.accuracy,
            "macro_f1": dl_report.macro_f1,
            "weighted_f1": dl_report.weighted_f1,
            "benign_fpr": dl_report.false_positive_rate,
            "train_seconds": dl_train_seconds,
            "num_parameters": count_parameters(dl_model),
            "final_epoch_loss": epoch_losses[-1] if epoch_losses else float("nan"),
        },
        "note_mitm_capture_repair_skipped": CAPTURE_REPAIRS_SKIPPED_NOTE,
    }
    return summary, comparison_table, confusion_matrices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config YAML (default: configs/config.yaml)")
    parser.add_argument("--csv", default=None, help="Override config's data.dnn_csv_path")
    parser.add_argument("--sample-size", type=int, default=None, help="Override classifier_comparison.sample_size")
    parser.add_argument("--seed", type=int, default=None, help="Override config's global seed")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config.logging.level, config.logging.log_dir, config.logging.log_file)

    if args.sample_size is not None:
        config.classifier_comparison.sample_size = args.sample_size
    seed = args.seed if args.seed is not None else config.seed
    csv_path = args.csv or config.data.dnn_csv_path

    summary, comparison_table, confusion_matrices = run_comparison(config, csv_path, seed)

    output_dir = Path(config.evaluation.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_table.to_csv(output_dir / "classifier_comparison_per_class.csv", index=False)
    (output_dir / "classifier_comparison_summary.json").write_text(json.dumps(summary, indent=2))
    (output_dir / "classifier_comparison_confusion_matrices.json").write_text(json.dumps(confusion_matrices, indent=2))

    logger.info(
        "=== Boosting vs. DL classifier (sample=%d/%d rows, %d train / %d test) ===",
        summary["sample_size_actual"], summary["full_dataset_rows"], summary["train_rows"], summary["test_rows"],
    )
    logger.info(
        "Boosting:      accuracy=%.4f macro_f1=%.4f weighted_f1=%.4f benign_fpr=%.4f train=%.1fs size=%dB",
        summary["boosting"]["accuracy"], summary["boosting"]["macro_f1"], summary["boosting"]["weighted_f1"],
        summary["boosting"]["benign_fpr"], summary["boosting"]["train_seconds"], summary["boosting"]["model_size_bytes"],
    )
    logger.info(
        "DL classifier: accuracy=%.4f macro_f1=%.4f weighted_f1=%.4f benign_fpr=%.4f train=%.1fs params=%d",
        summary["dl_classifier"]["accuracy"], summary["dl_classifier"]["macro_f1"], summary["dl_classifier"]["weighted_f1"],
        summary["dl_classifier"]["benign_fpr"], summary["dl_classifier"]["train_seconds"], summary["dl_classifier"]["num_parameters"],
    )
    logger.info(
        "Wrote %s and %s",
        output_dir / "classifier_comparison_per_class.csv",
        output_dir / "classifier_comparison_summary.json",
    )


if __name__ == "__main__":
    main()
