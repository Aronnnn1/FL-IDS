"""Benign validation loss per round with and without the per-client z-score clip (project notes §4.3).

    python -m fl_ids.eval.clip_comparison --num-rounds 20 --output-dir results/clip

Same data, seed and pipeline (full, no attackers); only `data.normalized_clip` changes (10 vs. no clip).
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
from pathlib import Path

import pandas as pd

from fl_ids.data.pipeline import load_and_encode
from fl_ids.eval.common import build_evaluation_setup_from_arrays
from fl_ids.eval.variants import FULL_PIPELINE, train_variant
from fl_ids.utils.config import load_config
from fl_ids.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--real-csv-path", default="data/raw/DNN-EdgeIIoT-dataset.csv")
    parser.add_argument("--num-rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results/clip")
    args = parser.parse_args()
    setup_logging()
    base = load_config(args.config_path)
    X, y, encoder, _features, benign = load_and_encode(
        args.real_csv_path, base.data.capture_repairs, base.data.extended_features, base.data.feature_cache
    )
    rows = []
    for label, clip in (("clip 10", base.data.normalized_clip), ("no clip", None)):
        config = dataclasses.replace(base, data=dataclasses.replace(base.data, normalized_clip=clip))
        setup = build_evaluation_setup_from_arrays(X, y, list(encoder.classes_), benign, config, args.seed)
        trained = train_variant(FULL_PIPELINE, setup, config, args.num_rounds, set(), args.seed)
        for record in trained.simulation.rounds:
            rows.append({"normalization": label, "round": record.round, "mean_val_loss": record.mean_val_loss})
        logger.info("%s: final mean_val_loss=%.4g", label, rows[-1]["mean_val_loss"])
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "clip_comparison.csv", index=False)
    print(df.pivot(index="round", columns="normalization", values="mean_val_loss").to_string())


if __name__ == "__main__":
    main()
