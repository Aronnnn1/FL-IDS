"""Pruning during federated training: the server re-prunes the global autoencoder every round (gradual, magnitude).

    python -m fl_ids.eval.pruning_fl --num-rounds 20 --output-dir results/pruning

Full pipeline, no attackers, same setup as the poisoning sweep's 0% point. Compared with the post-training pruning in
`fl_ids.eval.pruning`, the model here learns around the zeros. Thresholds are calibrated on the pruned final model.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from fl_ids.data.pipeline import load_and_encode
from fl_ids.eval.common import build_evaluation_setup_from_arrays
from fl_ids.eval.pruning import sizes
from fl_ids.eval.variants import FULL_PIPELINE, score_on_test_set, train_variant
from fl_ids.utils.config import load_config
from fl_ids.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)
SPARSITIES = (0.0, 0.5, 0.7, 0.8, 0.9)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--real-csv-path", default="data/raw/DNN-EdgeIIoT-dataset.csv")
    parser.add_argument("--num-rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results/pruning")
    parser.add_argument("--sparsities", nargs="*", type=float, default=list(SPARSITIES))
    args = parser.parse_args()
    setup_logging()
    config = load_config(args.config_path)
    X, y, encoder, _features, benign = load_and_encode(
        args.real_csv_path, config.data.capture_repairs, config.data.extended_features, config.data.feature_cache
    )
    setup = build_evaluation_setup_from_arrays(X, y, list(encoder.classes_), benign, config, args.seed)
    rows = []
    for sparsity in args.sparsities:
        trained = train_variant(FULL_PIPELINE, setup, config, args.num_rounds, set(), args.seed, prune_sparsity=sparsity)
        scores = score_on_test_set(trained, setup, config)
        scores.pop("per_class_recall")
        rows.append({"sparsity": sparsity, **sizes(trained.autoencoder), **scores,
                     "final_val_loss": trained.simulation.rounds[-1].mean_val_loss})
        logger.info("sparsity=%.2f cascade_macro=%.3f ae_alone=%.3f fpr=%.4f val_loss=%.4f", sparsity, scores["attack_macro_recall"],
                    scores["autoencoder_alone_attack_macro_recall"], scores["benign_fpr"], rows[-1]["final_val_loss"])
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "pruning_during_fl.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
