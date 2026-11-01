"""Adaptive-attacker test: the full pipeline under sign-flip vs. stealth attackers at several fractions.

    python -m fl_ids.eval.adaptive_attack --num-rounds 20 --output-dir results/adaptive

Same setup as the poisoning sweep (full pipeline, trust filter on); the only change is the attacker kind.
`malicious_client_survival_rate` is the share of attacker client-rounds the filter let through.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from fl_ids.data.pipeline import load_and_encode
from fl_ids.eval.common import build_evaluation_setup_from_arrays, select_malicious_clients
from fl_ids.eval.variants import FULL_PIPELINE, malicious_survival_rate, score_on_test_set, train_variant
from fl_ids.robustness.attackers import ATTACK_KINDS
from fl_ids.utils.config import load_config
from fl_ids.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)
FRACTIONS = (0.2, 0.3, 0.4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--real-csv-path", default="data/raw/DNN-EdgeIIoT-dataset.csv")
    parser.add_argument("--num-rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results/adaptive")
    args = parser.parse_args()

    setup_logging()
    config = load_config(args.config_path)
    X, y, encoder, _features, benign = load_and_encode(
        args.real_csv_path, config.data.capture_repairs, config.data.extended_features, config.data.feature_cache
    )
    setup = build_evaluation_setup_from_arrays(X, y, list(encoder.classes_), benign, config, args.seed)
    client_ids = list(setup.client_data)

    rows = []
    for attack in ATTACK_KINDS:
        for fraction in FRACTIONS:
            malicious = select_malicious_clients(client_ids, fraction, args.seed)
            trained = train_variant(FULL_PIPELINE, setup, config, args.num_rounds, malicious, args.seed, attack=attack)
            scores = score_on_test_set(trained, setup, config)
            scores.pop("per_class_recall")
            row = {
                "attack": attack, "malicious_fraction": fraction, "num_malicious_clients": len(malicious),
                **scores, "malicious_client_survival_rate": malicious_survival_rate(trained, malicious),
                "final_val_loss": trained.simulation.rounds[-1].mean_val_loss,
            }
            rows.append(row)
            logger.info("%s %.0f%%: attack_macro_recall=%.3f ae_alone=%.3f survival=%.3f val_loss=%.4g", attack,
                        100 * fraction, row["attack_macro_recall"], row["autoencoder_alone_attack_macro_recall"],
                        row["malicious_client_survival_rate"], row["final_val_loss"])
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "adaptive_attack.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
