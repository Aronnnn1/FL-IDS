"""Result charts for the FL-IDS report and slides. Every number is read from a result file."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
ACC = ROOT / "results" / "accuracy"
PRJ = ROOT / "results" / "project"          # original 91-feature federated results
EXT = ROOT / "results" / "extended"         # same experiments, 130 features (current pipeline)
import os
PRES = os.environ.get("PRES") == "1"  # larger text for projected slides
FS = (lambda x: round(x * 1.35, 1)) if PRES else (lambda x: x)
OUT = Path(__file__).parent / ("out_pres" if PRES else "out")
OUT.mkdir(exist_ok=True)

# Validated categorical order (validate_palette.js, light surface: all checks pass)
C1, C2, C3, C4 = "#3A5BC7", "#0A9396", "#D64550", "#C98A0B"
INK, MUTED, GRID = "#1b1b1b", "#5B6770", "#E4E6EA"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})
if PRES:
    plt.rcParams.update({"font.size": 14, "axes.titlesize": 15, "xtick.labelsize": 13, "ytick.labelsize": 13,
                         "legend.fontsize": 13, "axes.labelsize": 14})


def load(name):
    return json.loads((ACC / f"{name}.json").read_text())


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def progression():
    stages = [
        ("Base features\n(current)", "base_grouped_s42"),
        ("+ service\nport", "base_svc_grouped_s42"),
        ("+ payload/URI\ncontent", "base_content_grouped_s42"),
        ("+ flow\nfeatures", "full_grouped_s42"),
        ("+ class\nweights (final)", "full_grouped_bal_s42"),
    ]
    acc = [load(n)["accuracy"] for _, n in stages]
    f1 = [load(n)["macro_f1"] for _, n in stages]
    x = np.arange(len(stages))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.axhline(0.95, color=C3, lw=1.3, ls="--")
    ax.text(len(stages) - 0.55, 0.951, "95% target", color=C3, fontsize=FS(9.5), ha="right", va="bottom")
    ax.plot(x, acc, "-o", color=C1, lw=2, ms=8, label="Accuracy")
    ax.plot(x, f1, "-o", color=C2, lw=2, ms=8, label="Macro F1")
    for i in range(len(x)):
        ax.annotate(f"{acc[i]:.3f}", (x[i], acc[i]), xytext=(0, 9), textcoords="offset points", ha="center",
                    fontsize=FS(9), color=INK)
        ax.annotate(f"{f1[i]:.3f}", (x[i], f1[i]), xytext=(0, -16), textcoords="offset points", ha="center",
                    fontsize=FS(9), color=INK)
    ax.set_xticks(x, [s for s, _ in stages])
    ax.set_ylim(0.86, 1.012)
    ax.set_ylabel("Score on held-out flows")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("LightGBM on all 1.9M rows, flow-grouped 80/20 split (seed 42)", fontsize=FS(11), color=INK, loc="left")
    save(fig, "accuracy_progression")


def per_class():
    before, after = load("base_grouped_s42"), load("full_grouped_bal_s42")
    classes = [c for c in before["classes"] if before["per_class"][c]["support"] and after["per_class"][c]["support"]]
    b = np.array([before["per_class"][c]["f1-score"] for c in classes])
    a = np.array([after["per_class"][c]["f1-score"] for c in classes])
    order = np.argsort(b)
    classes, b, a = [classes[i].replace("_", " ") for i in order], b[order], a[order]
    y = np.arange(len(classes))
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    for i in y:
        ax.plot([b[i], a[i]], [i, i], color=GRID, lw=3, zorder=1)
    ax.scatter(b, y, s=70, color=C1, zorder=3, label="Base features", edgecolor="white", lw=1.5)
    ax.scatter(a, y, s=70, color=C2, zorder=3, label="Final (content + flow + weights)", edgecolor="white", lw=1.5)
    for i in y:
        ax.text(1.012, i, f"{b[i]:.2f} → {a[i]:.2f}", va="center", fontsize=FS(9), color=INK)
    ax.set_yticks(y, classes)
    ax.set_xlim(0.6, 1.0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Per-class F1 (flow-grouped split, seed 42)")
    ax.legend(loc="lower left", frameon=False, bbox_to_anchor=(0, 1.0), ncol=2)
    save(fig, "per_class_f1")


def confusion():
    r = load("full_grouped_bal_s42")
    cm = np.array(r["confusion_matrix"], dtype=float)
    keep = [i for i, c in enumerate(r["classes"]) if cm[i].sum() > 0]
    cm = cm[np.ix_(keep, keep)]
    names = [r["classes"][i].replace("_", " ") for i in keep]
    norm = cm / cm.sum(axis=1, keepdims=True)
    cmap = LinearSegmentedColormap.from_list("blue", ["#FFFFFF", "#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    ax.grid(False)
    im = ax.imshow(norm, cmap=cmap, vmin=0, vmax=1)
    for i in range(len(names)):
        for j in range(len(names)):
            if norm[i, j] >= 0.005:
                ax.text(j, i, f"{norm[i, j]:.2f}" if norm[i, j] < 0.995 else "1", ha="center", va="center",
                        fontsize=FS(7.5), color="white" if norm[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(names)), names, rotation=55, ha="right", fontsize=FS(8.5))
    ax.set_yticks(range(len(names)), names, fontsize=FS(8.5))
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Share of true class (row-normalised)")
    save(fig, "confusion_final")


def seeds():
    rows = []
    for split, pat in [("Random", "full_bal_s{}"), ("Flow-grouped", "full_grouped_bal_s{}")]:
        for s in (42, 43, 44):
            r = load(pat.format(s))
            rows.append((split, s, r["accuracy"], r["macro_f1"]))
    return pd.DataFrame(rows, columns=["split", "seed", "accuracy", "macro_f1"])


def poisoning():
    d = pd.read_csv(EXT / "poisoning_resistance_sweep.csv")
    old = pd.read_csv(PRJ / "poisoning_resistance_sweep.csv")
    xcol = [c for c in d.columns if "fraction" in c][0]
    x = d[xcol] * 100
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    series = [("attack_macro_recall", "Attack macro-recall", C1), ("zero_day_macro_recall", "Zero-day macro-recall", C2),
              ("autoencoder_alone_attack_macro_recall", "Autoencoder-alone recall", C3)]
    for col, lab, c in series:
        ax.plot(x, d[col], "-o", color=c, lw=2, ms=7, label=lab)
        ax.annotate(f"{d[col].iloc[-1]:.2f}", (x.iloc[-1], d[col].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=FS(9), color=INK)
    ax.set_xlabel("Malicious clients (%)")
    ax.set_ylabel("Recall")
    ax.set_ylim(-0.03, 1.0)
    ax.set_xticks(x)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("Detection vs. poisoning (full pipeline, 130 features)", fontsize=FS(11), loc="left", color=INK)
    ax = axes[1]
    surv_col = [c for c in d.columns if "survival" in c][0]
    s = d[d[surv_col].notna()]
    bars = ax.bar(s[xcol] * 100, s[surv_col], width=6, color=C4)
    for bx, v in zip(s[xcol] * 100, s[surv_col]):
        ax.text(bx, v + 0.02, f"{v:.2f}", ha="center", fontsize=FS(9), color=INK)
    ax.set_xticks(s[xcol] * 100)
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("Malicious clients (%)")
    ax.set_ylabel("Share passing the filter")
    ax.set_title("Malicious-client survival", fontsize=FS(11), loc="left", color=INK)
    fig.tight_layout()
    save(fig, "poisoning_sweep")


def zero_day():
    d = pd.read_csv(EXT / "zero_day_holdout.csv")
    cls = [c for c in d.columns if "class" in c][0]
    bo = [c for c in d.columns if c.startswith("boosting")][0]
    ca = [c for c in d.columns if c.startswith("cascade") and "fpr" not in c and "benign" not in c][0]
    d = d.sort_values(bo)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    for i, (b, c) in enumerate(zip(d[bo], d[ca])):
        ax.plot([b, c], [i, i], color=GRID, lw=3, zorder=1)
    ax.scatter(d[bo], y, s=70, color=C1, zorder=3, label="Boosting only", edgecolor="white", lw=1.5)
    ax.scatter(d[ca], y, s=70, color=C2, zorder=3, label="Cascade (boosting + autoencoder)", edgecolor="white", lw=1.5)
    for i, (b, c) in enumerate(zip(d[bo], d[ca])):
        ax.text(1.035, i, f"{b:.2f} → {c:.2f}", va="center", fontsize=FS(9), color=INK)
    ax.set_yticks(y, [s.replace("_", " ") for s in d[cls]])
    ax.set_xlim(0, 1.0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Detection rate on the held-out (never-seen) class")
    ax.legend(loc="lower left", frameon=False, bbox_to_anchor=(0, 1.0), ncol=2)
    save(fig, "zero_day")
    return d, bo, ca


def zero_day_compare():
    new = pd.read_csv(EXT / "zero_day_holdout.csv").set_index("holdout_class")
    old = pd.read_csv(PRJ / "zero_day_holdout.csv").set_index("holdout_class")
    cls = new.sort_values("cascade_detection_rate").index.tolist()
    o, n = old.loc[cls, "cascade_detection_rate"].to_numpy(), new.loc[cls, "cascade_detection_rate"].to_numpy()
    y = np.arange(len(cls))
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    for i in y:
        ax.plot([o[i], n[i]], [i, i], color=GRID, lw=3, zorder=1)
    ax.scatter(o, y, s=70, color=C1, zorder=3, label="Cascade, original 91 features", edgecolor="white", lw=1.5)
    ax.scatter(n, y, s=70, color=C2, zorder=3, label="Cascade, 130 features", edgecolor="white", lw=1.5)
    for i in y:
        ax.text(1.035, i, f"{o[i]:.2f} \u2192 {n[i]:.2f}", va="center", fontsize=FS(9), color=INK)
    ax.set_yticks(y, [c.replace("_", " ") for c in cls])
    ax.set_xlim(0, 1.0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Cascade detection rate on the held-out (never-seen) class")
    ax.legend(loc="lower left", frameon=False, bbox_to_anchor=(0, 1.0), ncol=2)
    save(fig, "zero_day_compare")


def ablation():
    new = pd.read_csv(EXT / "ablation_table.csv").set_index("variant")
    old = pd.read_csv(PRJ / "ablation_table.csv").set_index("variant")
    names = {"full_pipeline": "Full pipeline", "plain_fedavg": "Plain FedAvg", "trimmed_mean_only": "Trimmed mean only",
             "autoencoder_only": "Autoencoder only", "boosting_only": "Boosting only"}
    order = list(names)
    y = np.arange(len(order))
    h = 0.38
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, col, title in [(axes[0], "attack_macro_recall", "Known-attack macro-recall"),
                           (axes[1], "zero_day_macro_recall", "Zero-day macro-recall")]:
        o, n = old.loc[order, col].to_numpy(), new.loc[order, col].to_numpy()
        ax.barh(y - h / 2, o, height=h, color=C1, label="Original 91 features")
        ax.barh(y + h / 2, n, height=h, color=C2, label="130 features (current)")
        for i in range(len(order)):
            ax.text(o[i] + 0.01, y[i] - h / 2, f"{o[i]:.3f}", va="center", fontsize=FS(8.5), color=INK)
            ax.text(n[i] + 0.01, y[i] + h / 2, f"{n[i]:.3f}", va="center", fontsize=FS(8.5), color=INK)
        ax.set_xlim(0, 1.12)
        ax.set_title(title, fontsize=FS(11), loc="left", color=INK)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [names[v] for v in order])
    axes[0].invert_yaxis()
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper right", ncol=2, frameon=False, fontsize=FS(9.5))
    fig.suptitle("Ablation at 30% sign-flip attackers (20 rounds, seed 42)", x=0.01, ha="left", fontsize=FS(11), color=MUTED)
    fig.tight_layout()
    save(fig, "ablation")


if __name__ == "__main__":
    progression()
    per_class()
    confusion()
    poisoning()
    zero_day()
    zero_day_compare()
    ablation()
    print(seeds().to_string())
