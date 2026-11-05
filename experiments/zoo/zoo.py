"""Model zoo on Edge-IIoTset: many ML and DL classifiers, one split, one metric path.

Same rows, features, dedup and connection-grouped split as experiments/accuracy/train_eval.py
(feature set "full", 130 features, StratifiedGroupKFold by connection, seed 42, 10% of train held
out for validation). Hyperparameters are tuned on the validation rows only; the test rows are
scored once per model with the chosen settings. To keep slow learners feasible, every model trains
on the same class-capped stratified sample of the training rows (default 500,000); the test set is
the full connection-grouped test split.

Usage: python experiments/zoo/zoo.py [--seed 42] [--cap 500000] [--only name1,name2]
Writes experiments/zoo/results/<model>_s<seed>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fl_ids.data.pipeline import CATEGORICAL_COLUMNS, TARGET_COLUMN  # noqa: E402
from fl_ids.data.sampling import capped_stratified_sample_indices  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("zoo")
OUT = Path("experiments/zoo/results")
FEATURES = Path("experiments/accuracy/features.parquet")
NON_FEATURES = {TARGET_COLUMN, "flow_id"}
import os
THREADS = int(os.environ.get("ZOO_THREADS", "16"))


def load(seed: int, cap: int, featset: str = "full"):
    df = pd.read_parquet(FEATURES)
    all_cols = df.columns.tolist()
    base = [c for c in all_cols if not c.startswith(("c_", "f_", "svc_")) and c not in NON_FEATURES]
    cols = base + ["svc_port"] + [c for c in all_cols if c.startswith(("c_", "f_"))] if featset == "full" else base
    df = df[cols + [TARGET_COLUMN, "flow_id"]]
    cats = [c for c in CATEGORICAL_COLUMNS if c in cols]
    df = pd.get_dummies(df, columns=cats)
    feat_cols = [c for c in df.columns if c not in NON_FEATURES]
    df = df.drop_duplicates(subset=feat_cols + [TARGET_COLUMN]).reset_index(drop=True)
    classes = sorted(df[TARGET_COLUMN].unique())
    y = df[TARGET_COLUMN].map({c: i for i, c in enumerate(classes)}).to_numpy()
    X = df[feat_cols].astype(np.float32).to_numpy()
    idx = np.arange(len(y))
    sgk = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    f_tr, f_te = next(sgk.split(idx, y, groups=df["flow_id"].to_numpy()))
    tr, te = idx[f_tr], idx[f_te]
    tr, va = train_test_split(tr, test_size=0.1, random_state=seed, stratify=y[tr])
    # same capped sample for every model
    sub = capped_stratified_sample_indices(y[tr], cap, seed)
    tr_small = tr[np.sort(sub)]
    vsub = capped_stratified_sample_indices(y[va], 60000, seed)
    va_small = va[np.sort(vsub)]
    log.info("rows %d, train(full) %d, train(zoo) %d, val(zoo) %d, test %d, features %d",
             len(y), len(tr), len(tr_small), len(va_small), len(te), X.shape[1])
    return X, y, classes, tr_small, va_small, te, len(tr)


def score(y_true, y_pred, classes, benign_idx):
    present = sorted(set(y_true.tolist()))
    benign = y_true == benign_idx
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=present, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "benign_fpr": float((y_pred[benign] != benign_idx).mean()),
        "per_class_f1": {classes[i]: float(v) for i, v in zip(present, f1_score(y_true, y_pred, labels=present, average=None))},
    }


# ---------------------------------------------------------------- torch models
def torch_models():
    import torch
    import torch.nn as nn

    class MLP(nn.Module):
        def __init__(self, d, k, h=(256, 128)):
            super().__init__()
            layers, p = [], d
            for w in h:
                layers += [nn.Linear(p, w), nn.ReLU()]
                p = w
            layers.append(nn.Linear(p, k))
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            return self.net(x)

    class CNN(nn.Module):
        def __init__(self, d, k):
            super().__init__()
            self.c = nn.Sequential(nn.Conv1d(1, 32, 5, padding=2), nn.ReLU(), nn.MaxPool1d(2),
                                   nn.Conv1d(32, 64, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(8))
            self.f = nn.Sequential(nn.Flatten(), nn.Linear(64 * 8, 128), nn.ReLU(), nn.Linear(128, k))

        def forward(self, x):
            return self.f(self.c(x.unsqueeze(1)))

    class GRU(nn.Module):
        def __init__(self, d, k):
            super().__init__()
            self.g = nn.GRU(1, 48, batch_first=True)
            self.o = nn.Linear(48, k)

        def forward(self, x):
            _, h = self.g(x.unsqueeze(2))
            return self.o(h[-1])

    return torch, nn, MLP, CNN, GRU


def fit_torch(kind, Xtr, ytr, Xva, yva, Xte, k, seed, epochs, lr=2e-3, bs=1024, max_rows=None):
    torch, nn, MLP, CNN, GRU = torch_models()
    torch.manual_seed(seed)
    torch.set_num_threads(THREADS)
    if max_rows and len(Xtr) > max_rows:
        rng = np.random.default_rng(seed)
        keep = rng.choice(len(Xtr), max_rows, replace=False)
        Xtr, ytr = Xtr[keep], ytr[keep]
    d = Xtr.shape[1]
    net = {"mlp": MLP, "cnn1d": CNN, "gru": GRU}[kind](d, k)
    counts = np.bincount(ytr, minlength=k).astype(np.float32)
    w = torch.tensor(np.sqrt(counts.max() / np.maximum(counts, 1)))
    lossf = nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr).long()
    best, best_state = -1, None
    t0 = time.time()
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), bs):
            b = perm[i:i + bs]
            opt.zero_grad()
            lossf(net(Xt[b]), yt[b]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            pv = torch.cat([net(torch.from_numpy(Xva[i:i + 8192])).argmax(1) for i in range(0, len(Xva), 8192)]).numpy()
        f = f1_score(yva, pv, average="macro")
        log.info("%s epoch %d val macro F1 %.4f", kind, ep + 1, f)
        if f > best:
            best, best_state = f, {a: b.clone() for a, b in net.state_dict().items()}
    train_s = time.time() - t0
    net.load_state_dict(best_state)
    net.eval()
    t1 = time.time()
    with torch.no_grad():
        pred = torch.cat([net(torch.from_numpy(Xte[i:i + 8192])).argmax(1) for i in range(0, len(Xte), 8192)]).numpy()
    infer = time.time() - t1
    nparams = sum(p.numel() for p in net.parameters())
    return pred, train_s, infer, {"parameters": int(nparams), "val_macro_f1": float(best), "epochs": epochs, "train_rows_used": int(len(Xtr))}


# ---------------------------------------------------------------- sklearn-style models
def candidates(name, k, seed):
    """Return list of (config dict, factory) pairs; tuned on validation macro F1."""
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.svm import LinearSVC
    from sklearn.tree import DecisionTreeClassifier

    if name == "decision_tree":
        return [({"max_depth": d}, (lambda d=d: DecisionTreeClassifier(max_depth=d, class_weight="balanced", random_state=seed))) for d in (None, 20)]
    if name == "random_forest":
        return [({"n_estimators": 200, "min_samples_leaf": m}, (lambda m=m: RandomForestClassifier(200, min_samples_leaf=m, n_jobs=THREADS, class_weight="balanced_subsample", random_state=seed))) for m in (1, 3)]
    if name == "extra_trees":
        return [({"n_estimators": 200, "min_samples_leaf": m}, (lambda m=m: ExtraTreesClassifier(200, min_samples_leaf=m, n_jobs=THREADS, class_weight="balanced_subsample", random_state=seed))) for m in (1, 3)]
    if name == "hist_gradient_boosting":
        return [({"max_leaf_nodes": n, "learning_rate": 0.1, "max_iter": 200}, (lambda n=n: HistGradientBoostingClassifier(max_leaf_nodes=n, max_iter=200, early_stopping=True, class_weight="balanced", random_state=seed))) for n in (63,)]
    if name == "logistic_regression":
        return [({"C": c}, (lambda c=c: LogisticRegression(C=c, max_iter=300, class_weight="balanced", n_jobs=THREADS))) for c in (0.1, 1.0)]
    if name == "linear_svm":
        from sklearn.linear_model import SGDClassifier
        return [({"alpha": a, "loss": "hinge"}, (lambda a=a: SGDClassifier(loss="hinge", alpha=a, class_weight="balanced", max_iter=30, tol=None, n_jobs=THREADS, random_state=seed))) for a in (1e-5, 1e-4)]
    if name == "gaussian_nb":
        return [({}, GaussianNB)]
    if name == "knn":
        return [({"k": kk}, (lambda kk=kk: KNeighborsClassifier(kk, weights="distance", n_jobs=THREADS))) for kk in (5, 15)]
    if name == "svm_rbf_40k":
        from sklearn.svm import SVC
        return [({"C": c, "gamma": "scale"}, (lambda c=c: SVC(C=c, kernel="rbf", class_weight="balanced"))) for c in (1.0, 10.0)]
    raise KeyError(name)


def run_boosters(name, Xtr, ytr, Xva, yva, Xte, k, seed):
    """lightgbm / xgboost / catboost with early stopping on the validation rows."""
    out = []
    counts = np.bincount(ytr, minlength=k).astype(float)
    cw = np.sqrt(counts.max() / np.maximum(counts, 1))
    w = cw[ytr]
    if name == "lightgbm":
        import lightgbm as lgb
        for leaves in (31, 63, 127):
            p = {"objective": "multiclass", "num_class": k, "learning_rate": 0.1, "num_leaves": leaves, "lambda_l2": 1.0,
                 "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "num_threads": THREADS, "seed": seed, "verbose": -1}
            t0 = time.time()
            b = lgb.train(p, lgb.Dataset(Xtr, ytr, weight=w), 1000, valid_sets=[lgb.Dataset(Xva, yva)],
                          callbacks=[lgb.early_stopping(50, verbose=False)])
            ts = time.time() - t0
            vf = f1_score(yva, b.predict(Xva).argmax(1), average="macro")
            out.append(({"num_leaves": leaves, "best_iteration": b.best_iteration}, vf, ts, b, lambda m, X: m.predict(X).argmax(1)))
    elif name == "xgboost":
        import xgboost as xgb
        for depth in (6, 10):
            m = xgb.XGBClassifier(n_estimators=1000, max_depth=depth, learning_rate=0.1, tree_method="hist", n_jobs=THREADS,
                                  subsample=0.8, colsample_bytree=0.8, early_stopping_rounds=50, random_state=seed, eval_metric="mlogloss")
            t0 = time.time()
            m.fit(Xtr, ytr, sample_weight=w, eval_set=[(Xva, yva)], verbose=False)
            ts = time.time() - t0
            vf = f1_score(yva, m.predict(Xva), average="macro")
            out.append(({"max_depth": depth, "best_iteration": int(m.best_iteration)}, vf, ts, m, lambda m, X: m.predict(X)))
    elif name == "catboost":
        from catboost import CatBoostClassifier
        for depth in (6, 8):
            m = CatBoostClassifier(iterations=800, depth=depth, learning_rate=0.15, loss_function="MultiClass", thread_count=THREADS,
                                   random_seed=seed, verbose=0, early_stopping_rounds=50)
            t0 = time.time()
            m.fit(Xtr, ytr, sample_weight=w, eval_set=(Xva, yva))
            ts = time.time() - t0
            vf = f1_score(yva, m.predict(Xva).ravel().astype(int), average="macro")
            out.append(({"depth": depth, "best_iteration": int(m.get_best_iteration())}, vf, ts, m, lambda m, X: m.predict(X).ravel().astype(int)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cap", type=int, default=500000)
    ap.add_argument("--only", default="")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--featset", default="full", choices=["full", "base"])
    a = ap.parse_args()
    global OUT
    if a.featset == "base":
        OUT = Path("experiments/zoo/results_base91")
    if a.outdir:
        OUT = Path(a.outdir)
    OUT.mkdir(parents=True, exist_ok=True)
    X, y, classes, tr, va, te, n_train_full = load(a.seed, a.cap, a.featset)
    k = len(classes)
    benign = classes.index("Normal")
    sc = StandardScaler().fit(X[tr])
    Xs = {"raw": X, "std": None}
    Xstd = sc.transform(X).astype(np.float32)
    Xtr, ytr, Xva, yva, Xte, yte = X[tr], y[tr], X[va], y[va], X[te], y[te]
    Str, Sva, Ste = Xstd[tr], Xstd[va], Xstd[te]

    order = ["lightgbm", "xgboost", "catboost", "hist_gradient_boosting", "random_forest", "extra_trees", "decision_tree",
             "gaussian_nb", "logistic_regression", "linear_svm", "knn", "mlp", "cnn1d", "gru", "svm_rbf_40k"]
    want = [m for m in order if not a.only or m in a.only.split(",")]
    meta = {"seed": a.seed, "train_rows_zoo": int(len(tr)), "val_rows_zoo": int(len(va)), "test_rows": int(len(te)),
            "train_rows_full_split": int(n_train_full), "features": int(X.shape[1]), "classes": classes}
    for name in want:
        path = OUT / f"{name}_s{a.seed}.json"
        if path.exists():
            log.info("skip %s (done)", name)
            continue
        log.info("=== %s", name)
        res = {**meta, "model": name}
        try:
            if name in ("lightgbm", "xgboost", "catboost"):
                cands = run_boosters(name, Xtr, ytr, Xva, yva, Xte, k, a.seed)
                cfg, vf, ts, model, pf = max(cands, key=lambda c: c[1])
                t1 = time.time()
                pred = pf(model, Xte)
                inf = time.time() - t1
                res.update(config=cfg, val_macro_f1=float(vf), tried=[{"config": c[0], "val_macro_f1": float(c[1])} for c in cands],
                           train_seconds=float(ts), inference_seconds=float(inf))
            elif name in ("mlp", "cnn1d", "gru"):
                ep, mr = {"mlp": (15, None), "cnn1d": (8, None), "gru": (20, 150000)}[name]
                pred, ts, inf, extra = fit_torch(name, Str, ytr, Sva, yva, Ste, k, a.seed, ep, max_rows=mr)
                res.update(train_seconds=float(ts), inference_seconds=float(inf), **extra)
            else:
                std = name in ("logistic_regression", "linear_svm", "knn", "svm_rbf_40k", "gaussian_nb")
                A, B, C = (Str, Sva, Ste) if std else (Xtr, Xva, Xte)
                yy = ytr
                if name == "svm_rbf_40k":
                    sub = capped_stratified_sample_indices(ytr, 40000, a.seed)
                    A, yy = A[sub], ytr[sub]
                cs = candidates(name, k, a.seed)
                best = None
                tried = []
                for cfg, fac in cs:
                    m = fac()
                    t0 = time.time()
                    m.fit(A, yy)
                    ts = time.time() - t0
                    vf = f1_score(yva, m.predict(B), average="macro")
                    tried.append({"config": cfg, "val_macro_f1": float(vf), "train_seconds": float(ts)})
                    log.info("%s %s val %.4f (%.0fs)", name, cfg, vf, ts)
                    if best is None or vf > best[0]:
                        best = (vf, cfg, ts, m)
                vf, cfg, ts, m = best
                t1 = time.time()
                pred = m.predict(C)
                inf = time.time() - t1
                res.update(config=cfg, val_macro_f1=float(vf), tried=tried, train_seconds=float(ts), inference_seconds=float(inf),
                           train_rows_used=int(len(yy)))
            res.update(score(yte, pred, classes, benign))
            res["inference_us_per_row"] = res["inference_seconds"] / len(yte) * 1e6
            res["confusion_matrix"] = confusion_matrix(yte, pred, labels=list(range(k))).tolist()
            log.info("%s test: acc %.4f macroF1 %.4f train %.0fs", name, res["accuracy"], res["macro_f1"], res["train_seconds"])
        except Exception as e:  # keep going, record the failure
            log.exception("failed %s", name)
            res["error"] = repr(e)
        path.write_text(json.dumps(res))


if __name__ == "__main__":
    main()
