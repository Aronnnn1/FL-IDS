"""Train/evaluate LightGBM on one feature set over the full cleaned dataset.

For a feature set: one-hot encode the project's categoricals, drop exact
duplicate (features + label) rows -- the project's dedup rule, applied to
this feature set -- then:

  * ambiguity ceiling: best accuracy / macro recall any per-row classifier
    could reach, since identical feature vectors with different labels can't
    be told apart
  * LightGBM on a stratified 80/20 split (natural class distribution), with
    early stopping on 10% of the training rows
  * optionally the same on a flow-grouped 80/20 split (no connection in both
    train and test), to check the result isn't connection memorization

Usage: python experiments/accuracy/train_eval.py <feature_set> [--grouped] [--seed N]
Writes experiments/accuracy/results/<feature_set>[_grouped]_s<seed>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fl_ids.data.pipeline import CATEGORICAL_COLUMNS, TARGET_COLUMN  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_eval")

FEATURES = Path("experiments/accuracy/features.parquet")
RESULTS = Path("experiments/accuracy/results")
NON_FEATURES = {TARGET_COLUMN, "flow_id"}


def select_columns(all_cols: list[str], feature_set: str) -> list[str]:
    base = [c for c in all_cols if not c.startswith(("c_", "f_", "svc_")) and c not in NON_FEATURES]
    groups = {
        "base": base,
        "base_svc": base + ["svc_port"],
        "base_content": base + ["svc_port"] + [c for c in all_cols if c.startswith("c_")],
        "full": base + ["svc_port"] + [c for c in all_cols if c.startswith(("c_", "f_"))],
    }
    return groups[feature_set]


def ambiguity_ceiling(X: pd.DataFrame, y: np.ndarray, n_classes: int) -> dict:
    h = pd.util.hash_pandas_object(X, index=False).to_numpy()
    tab = pd.crosstab(h, y)
    best = tab.max(axis=1).sum()
    winner = tab.idxmax(axis=1)
    per_class_recall = []
    for c in range(n_classes):
        if c in tab.columns:
            per_class_recall.append(float(tab.loc[winner == c, c].sum() / tab[c].sum()))
    ambiguous_rows = int(tab[(tab > 0).sum(axis=1) > 1].values.sum())
    return {
        "ceiling_accuracy": float(best / len(y)),
        "ceiling_macro_recall": float(np.mean(per_class_recall)),
        "ambiguous_rows": ambiguous_rows,
        "ambiguous_share": ambiguous_rows / len(y),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("feature_set")
    p.add_argument("--grouped", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rounds", type=int, default=2000)
    p.add_argument("--leaves", type=int, default=63)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--train-fraction", type=float, default=0.0,
                   help="keep only this fraction of all rows for training (stratified), e.g. 0.05 = the server calibration set")
    p.add_argument("--temporal", action="store_true",
                   help="per-class time-ordered split: each class's earliest ~80%% of flows (CSV row order is capture order "
                        "within a class) train, the latest ~20%% test; whole flows stay on one side")
    p.add_argument("--balance", action="store_true", help="sqrt inverse-frequency class weights")
    p.add_argument("--sample", type=int, default=0, help="capped stratified sample size (0 = all rows)")
    args = p.parse_args()
    t0 = time.time()

    df = pd.read_parquet(FEATURES)
    cols = select_columns(df.columns.tolist(), args.feature_set)
    df = df[cols + [TARGET_COLUMN, "flow_id"]]
    cats = [c for c in CATEGORICAL_COLUMNS if c in cols]
    df = pd.get_dummies(df, columns=cats)
    feat_cols = [c for c in df.columns if c not in NON_FEATURES]
    n_before = len(df)
    df = df.drop_duplicates(subset=feat_cols + [TARGET_COLUMN]).reset_index(drop=True)
    log.info("%s: %d features, %d -> %d rows after dedup", args.feature_set, len(feat_cols), n_before, len(df))

    classes = sorted(df[TARGET_COLUMN].unique())
    y = df[TARGET_COLUMN].map({c: i for i, c in enumerate(classes)}).to_numpy()
    X = df[feat_cols].astype(np.float32)
    X.columns = [f"x{i}" for i in range(len(feat_cols))]  # LightGBM rejects JSON chars in names
    ceiling = ambiguity_ceiling(X, y, len(classes))
    log.info("ceiling: %s", ceiling)

    idx = np.arange(len(y))
    if args.sample:
        from fl_ids.data.sampling import capped_stratified_sample_indices
        idx = np.sort(capped_stratified_sample_indices(y, args.sample, args.seed))
    if args.temporal:
        # Rows are in capture order within a class (checked: time is non-decreasing in row order for every class).
        # Order each class's flows by their first row and send the last ~20% of its rows (whole flows) to test.
        pos = np.arange(len(y))
        flow = df["flow_id"].to_numpy()
        test_mask = np.zeros(len(y), dtype=bool)
        for c in range(len(classes)):
            rows = idx[y[idx] == c]
            first = pd.Series(pos[rows]).groupby(flow[rows]).min()
            sizes = pd.Series(1, index=rows).groupby(flow[rows]).sum().reindex(first.index)
            order = first.sort_values().index
            cum = sizes.loc[order].cumsum().to_numpy()
            late = set(order[cum > 0.8 * cum[-1]])
            test_mask[rows[np.isin(flow[rows], list(late))]] = True
        te = idx[test_mask[idx]]
        tr = idx[~test_mask[idx]]
    elif args.grouped:
        # 5 folds -> ~20% test; every class present on both sides, no flow on both
        sgk = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=args.seed)
        f_tr, f_te = next(sgk.split(idx, y[idx], groups=df["flow_id"].to_numpy()[idx]))
        tr, te = idx[f_tr], idx[f_te]
    else:
        tr, te = train_test_split(idx, test_size=0.2, random_state=args.seed, stratify=y[idx])
    if args.train_fraction:
        keep = int(args.train_fraction * len(idx))
        tr, _ = train_test_split(tr, train_size=keep, random_state=args.seed, stratify=y[tr])
    tr, va = train_test_split(tr, test_size=0.1, random_state=args.seed, stratify=y[tr])

    params = {
        "objective": "multiclass",
        "num_class": len(classes),
        "learning_rate": args.lr,
        "num_leaves": args.leaves,
        "min_sum_hessian_in_leaf": 1.0,
        "lambda_l2": 1.0,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "num_threads": 4,
        "seed": args.seed,
        "verbose": -1,
    }
    w_tr = w_va = None
    if args.balance:
        counts = np.bincount(y[tr], minlength=len(classes)).astype(float)
        cw = np.sqrt(counts.max() / np.maximum(counts, 1))
        w_tr, w_va = cw[y[tr]], cw[y[va]]
    dtr = lgb.Dataset(X.iloc[tr], y[tr], weight=w_tr, free_raw_data=True)
    dva = lgb.Dataset(X.iloc[va], y[va], weight=w_va, reference=dtr)
    t1 = time.time()
    booster = lgb.train(
        params,
        dtr,
        num_boost_round=args.rounds,
        valid_sets=[dva],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)],
    )
    train_s = time.time() - t1
    pred = booster.predict(X.iloc[te]).argmax(axis=1)
    yt = y[te]

    acc = accuracy_score(yt, pred)
    present = sorted(set(yt.tolist()))  # a class with no test rows (MITM is one flow) can't be scored
    mf1 = f1_score(yt, pred, labels=present, average="macro")
    report = classification_report(yt, pred, labels=list(range(len(classes))), target_names=classes, output_dict=True, zero_division=0)
    imp = pd.Series(booster.feature_importance("gain"), index=feat_cols).sort_values(ascending=False)
    res = {
        "feature_set": args.feature_set,
        "split": "temporal_per_class" if args.temporal else ("flow_grouped" if args.grouped else "stratified_random"),
        "seed": args.seed,
        "n_features": len(feat_cols),
        "rows_before_dedup": n_before,
        "rows": len(y),
        "sample": args.sample,
        "balanced_weights": args.balance,
        "train_fraction": args.train_fraction,
        "train_rows": len(tr),
        "val_rows": len(va),
        "test_rows": len(te),
        **ceiling,
        "classes_scored": [classes[i] for i in present],
        "accuracy": acc,
        "macro_f1": mf1,
        "weighted_f1": f1_score(yt, pred, average="weighted"),
        "best_iteration": booster.best_iteration,
        "train_seconds": train_s,
        "params": params,
        "per_class": {c: report[c] for c in classes},
        "confusion_matrix": confusion_matrix(yt, pred, labels=list(range(len(classes)))).tolist(),
        "classes": classes,
        "top_features": imp.head(25).round(1).to_dict(),
        "total_seconds": time.time() - t0,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = f"{args.feature_set}{'_grouped' if args.grouped else ''}{'_temporal' if args.temporal else ''}{f'_n{args.sample}' if args.sample else ''}{'_bal' if args.balance else ''}{f'_tf{args.train_fraction}' if args.train_fraction else ''}_s{args.seed}"
    (RESULTS / f"{name}.json").write_text(json.dumps(res, indent=1))
    booster.save_model(str(RESULTS / f"{name}.model.txt"))
    np.savez_compressed(RESULTS / f"{name}.pred.npz", test_idx=te, y_true=yt, y_pred=pred,
                        flow_id=df["flow_id"].to_numpy()[te])
    log.info("RESULT %s acc=%.4f macroF1=%.4f (ceiling acc=%.4f macroRecall=%.4f) iters=%d %.0fs",
             name, acc, mf1, ceiling["ceiling_accuracy"], ceiling["ceiling_macro_recall"],
             booster.best_iteration, time.time() - t0)
    for c in classes:
        log.info("  %-22s P=%.3f R=%.3f F1=%.3f n=%d", c, report[c]["precision"], report[c]["recall"],
                 report[c]["f1-score"], report[c]["support"])


if __name__ == "__main__":
    main()
