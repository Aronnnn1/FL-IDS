"""Diagnostic, not the harness: multi-seed check on the sweep's 20%-vs-30% anomaly.

PAPER_NOTES.md sect. 8.3 flags a single-seed (42) observation as
unexplained and not yet safe to claim as a trend: the poisoning sweep's
20% point had lower autoencoder-alone attack macro-recall (0.374) than
its 30% point (0.421) -- counter to the intuitive expectation that more
poisoning should hurt more, not less. This script reruns just those two
sweep points (skipping the expensive per-fraction zero-day retraining,
which isn't needed to check this specific metric) at two more seeds, to
see whether the 20% < 30% ordering holds or was a single-seed artifact.

    python -m fl_ids.eval.multiseed_check --num-rounds 20 --seeds 43 44
"""

from __future__ import annotations

import logging

import pandas as pd

from fl_ids.data.pipeline import load_and_encode
from fl_ids.eval.common import build_evaluation_setup_from_arrays
from fl_ids.eval.poisoning_sweep import run_poisoning_sweep

logger = logging.getLogger(__name__)


def run_multiseed_check(config, real_csv_path: str, num_rounds: int, seeds: list[int]) -> pd.DataFrame:
    config.evaluation.poisoning_fractions = [0.2, 0.3]
    rows = []
    for seed in seeds:
        X, y, label_encoder, _feature_names, benign_class = load_and_encode(real_csv_path, config.data.capture_repairs)
        class_names = list(label_encoder.classes_)
        setup = build_evaluation_setup_from_arrays(X, y, class_names, benign_class, config, seed)
        sweep_df = run_poisoning_sweep(setup, config, num_rounds=num_rounds, seed=seed)
        sweep_df.insert(0, "seed", seed)
        rows.append(sweep_df)
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from fl_ids.utils.config import load_config
    from fl_ids.utils.logging_setup import setup_logging

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--real-csv-path", default="data/raw/DNN-EdgeIIoT-dataset.csv")
    parser.add_argument("--num-rounds", type=int, default=20)
    parser.add_argument("--seeds", type=int, nargs="+", default=[43, 44])
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    run_config = load_config(args.config_path)
    setup_logging(run_config.logging.level, run_config.logging.log_dir, run_config.logging.log_file)
    output_dir = Path(args.output_dir or run_config.evaluation.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = run_multiseed_check(run_config, args.real_csv_path, args.num_rounds, args.seeds)
    out_path = output_dir / "multiseed_20_30_check.csv"
    df.to_csv(out_path, index=False)
    for _, row in df.iterrows():
        logger.info(
            "seed=%d fraction=%.2f: attack_macro_recall=%.3f autoencoder_alone=%.3f benign_fpr=%.4f",
            row["seed"], row["malicious_fraction"], row["attack_macro_recall"],
            row["autoencoder_alone_attack_macro_recall"], row["benign_fpr"],
        )
    logger.info("Wrote %s", out_path)
