"""Per-stage precision/recall/F1/AUROC per class (component 12), on real data.

The ablation/sweep/zero-day scripts (`fl_ids.eval.ablation`, `poisoning_sweep`,
`zero_day`) all score variants through `flag_attacks`/`detection_metrics` --
a binary "flagged as attack or not" framing that gives per-class recall,
but never precision or AUROC. This script fills that specific gap: it
trains the full pipeline once (0% attackers, matching the sweep's 0%
point) and calls `evaluate_boosting_alone`, `evaluate_autoencoder_alone`
and `evaluate_cascade` directly -- the richer per-stage report `fl_ids.
eval.metrics` already computes, just never previously written to a file.

    python -m fl_ids.eval.stage_report --num-rounds 20
"""

from __future__ import annotations

import logging
from pathlib import Path

from fl_ids.data.pipeline import load_and_encode
from fl_ids.eval.common import build_evaluation_setup_from_arrays, calibrate_client_thresholds, per_row_thresholds
from fl_ids.eval.metrics import (
    build_per_stage_table,
    evaluate_autoencoder_alone,
    evaluate_boosting_alone,
    evaluate_cascade,
)
from fl_ids.eval.simulation import run_simulated_fl_training

logger = logging.getLogger(__name__)


def run_stage_report(config, real_csv_path: str, num_rounds: int, seed: int):
    """Train the full pipeline at 0% attackers and score each stage's full per-class report.

    Returns:
        (combined per-class DataFrame, dict of headline stage_report_summary per stage).
    """
    X, y, label_encoder, _feature_names, benign_class = load_and_encode(real_csv_path, config.data.capture_repairs)
    class_names = list(label_encoder.classes_)
    setup = build_evaluation_setup_from_arrays(X, y, class_names, benign_class, config, seed)

    result = run_simulated_fl_training(
        setup.client_data, setup.boosting_model, len(class_names), benign_class, config,
        num_rounds=num_rounds, aggregation="trust_filtered", malicious_client_ids=set(),
        use_boosting_filter=True, seed=seed, boosting_updater=None,
    )
    autoencoder, thresholds = calibrate_client_thresholds(result.final_weights, setup, config)
    per_row_thr = per_row_thresholds(thresholds, setup.test_client_ids)

    boosting_report = evaluate_boosting_alone(
        result.final_boosting_model, setup.X_test_raw, setup.y_test, class_names, benign_class
    )
    ae_report = evaluate_autoencoder_alone(autoencoder, per_row_thr, setup.X_test_norm, setup.y_test, benign_class)
    cascade_report = evaluate_cascade(
        result.final_boosting_model, autoencoder, per_row_thr, setup.X_test_raw, setup.X_test_norm,
        setup.y_test, class_names, benign_class, config.cascade,
    )

    table = build_per_stage_table([boosting_report, ae_report, cascade_report])
    return table, {
        "boosting_alone": boosting_report,
        "autoencoder_alone": ae_report,
        "cascade_combined": cascade_report,
    }


if __name__ == "__main__":
    import argparse

    from fl_ids.utils.config import load_config
    from fl_ids.utils.logging_setup import setup_logging

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--real-csv-path", default="data/raw/DNN-EdgeIIoT-dataset.csv")
    parser.add_argument("--num-rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    run_config = load_config(args.config_path)
    setup_logging(run_config.logging.level, run_config.logging.log_dir, run_config.logging.log_file)
    output_dir = Path(args.output_dir or run_config.evaluation.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    table, reports = run_stage_report(run_config, args.real_csv_path, args.num_rounds, args.seed)
    out_path = output_dir / "per_class_stage_report.csv"
    table.to_csv(out_path, index=False)
    for name, report in reports.items():
        logger.info(
            "%s: accuracy=%.4f macro_f1=%.4f weighted_f1=%.4f benign_fpr=%.4f",
            name, report.accuracy, report.macro_f1, report.weighted_f1, report.false_positive_rate,
        )
    logger.info("Wrote %s", out_path)
