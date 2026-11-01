"""Figures listed in PAPER_NOTES §11 that did not exist yet. Every plot reads result files; nothing is typed in.

Run from the repo root in the VM:  venv/bin/python deliverables/scripts/new_figures.py
Writes PNGs to deliverables/report/figures/. A figure whose input is missing is skipped with a message.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/report/figures"
BLUE, ORANGE, GREY, RED = "#1F4E79", "#E08A1E", "#777777", "#B03A2E"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 110})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def attackers_of(run):
    manifest = json.load(open(ROOT / f"saved_models/attack_runs/{run}/manifest.json"))
    return {int(c) for c in manifest["training"]["malicious_client_ids"]}


def trust_and_similarity():
    for run, label in (("mal02", "20% attackers"), ("mal03", "30% attackers")):
        hist_path = ROOT / f"runs/attack_runs/{run}/history.json"
        if not hist_path.exists():
            print("skip trust/similarity", run)
            continue
        rounds = json.load(open(hist_path))["round_history"]
        bad = attackers_of(run)
        ids = sorted(int(c) for c in rounds[0]["trust_scores"])
        x = [r["round"] for r in rounds]
        fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.2))
        for cid in ids:
            trust = [r["trust_scores"].get(str(cid), np.nan) for r in rounds]
            a.plot(x, trust, color=RED if cid in bad else BLUE, alpha=0.9 if cid in bad else 0.45, lw=2 if cid in bad else 1.2)
            excluded = [r["round"] for r in rounds if str(cid) in r.get("exclusion_reasons", {})]
            a.scatter(excluded, [trust[i - 1] for i in excluded], marker="x", color=RED if cid in bad else GREY, s=22, zorder=3)
        a.axhline(0.5, color=GREY, ls="--", lw=1)
        a.text(x[-1], 0.51, "trust floor 0.5", ha="right", va="bottom", color=GREY, fontsize=9)
        a.set(xlabel="round", ylabel="trust score (EMA)", title=f"Trust per client, {label}")
        a.plot([], [], color=RED, label="attacker"); a.plot([], [], color=BLUE, alpha=0.5, label="honest")
        a.scatter([], [], marker="x", color=GREY, label="excluded that round")
        a.legend(frameon=False, fontsize=9, loc="lower left")
        honest = [[r["similarities"][str(c)] for c in ids if c not in bad and str(c) in r["similarities"]] for r in rounds]
        evil = [[r["similarities"][str(c)] for c in ids if c in bad and str(c) in r["similarities"]] for r in rounds]
        b.boxplot(honest, positions=np.array(x) - 0.17, widths=0.3, patch_artist=True, showfliers=False,
                  boxprops=dict(facecolor=BLUE, alpha=0.5), medianprops=dict(color="black"))
        b.boxplot(evil, positions=np.array(x) + 0.17, widths=0.3, patch_artist=True, showfliers=False,
                  boxprops=dict(facecolor=RED, alpha=0.6), medianprops=dict(color="black"))
        b.axhline(0, color=GREY, ls="--", lw=1)
        b.set(xlabel="round", ylabel="cosine similarity to the round's median update", title="Similarity per round")
        b.set_xticks(x[::2]); b.set_xticklabels(x[::2])
        fig.suptitle(f"Real Phase A (10 client processes, 20 rounds), {label}: attackers {sorted(bad)}", fontsize=11, y=1.02)
        save(fig, f"trust_{run}.png")


def partition_heatmap():
    run = ROOT / "runs/vmware_check/phase_a"
    files = sorted(run.glob("client_*.npz"), key=lambda p: int(p.stem.split("_")[1]))
    manifest = json.load(open(ROOT / "saved_models/vmware_check_phase_a/manifest.json"))
    names = manifest["class_names"]
    counts = np.zeros((len(files), len(names)), dtype=int)
    for i, f in enumerate(files):
        d = np.load(f)
        counts[i] = np.bincount(np.concatenate([d["y"], d["y_test"]]), minlength=len(names))
    fig, ax = plt.subplots(figsize=(11, 4.6))
    im = ax.imshow(np.log10(counts + 1), cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=60, ha="right")
    ax.set_yticks(range(len(files))); ax.set_yticklabels([f"client {i}" for i in range(len(files))])
    for i in range(counts.shape[0]):
        for j in range(counts.shape[1]):
            if counts[i, j]:
                ax.text(j, i, counts[i, j], ha="center", va="center", fontsize=7,
                        color="white" if np.log10(counts[i, j] + 1) > 2.2 else "black")
    fig.colorbar(im, ax=ax, label="log10(rows + 1)")
    ax.set_title("Rows per client and class: Dirichlet alpha = 0.3, seed 42, 10 clients (training + test slices)")
    save(fig, "partition_heatmap.png")


def reconstruction_errors():
    import sys
    sys.path.insert(0, str(ROOT))
    from fl_ids.eval.bundle_report import load_run_clients
    from fl_ids.models.autoencoder import reconstruction_error
    from fl_ids.orchestration.artifacts import load_phase_a_artifacts
    from fl_ids.utils.config import load_config

    config = load_config(str(ROOT / "configs/config_vmware_check.yaml"))
    art = load_phase_a_artifacts(ROOT / "saved_models/vmware_check_phase_a", config.boosting)
    clients = load_run_clients(ROOT / "runs/vmware_check/phase_a")
    benign, attack, thr = [], [], []
    for cid, d in clients.items():
        err = reconstruction_error(art.autoencoder, d["X_test"])
        isb = d["y_test"] == art.benign_class
        benign.append(err[isb]); attack.append(err[~isb])
        if np.isfinite(art.client_thresholds[cid]):
            thr.append(art.client_thresholds[cid])
    benign, attack = np.concatenate(benign), np.concatenate(attack)
    bins = np.logspace(-4, 2, 60)
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    ax.hist(np.clip(benign, bins[0], bins[-1]), bins=bins, density=True, alpha=0.6, color=BLUE, label=f"normal ({len(benign):,} test rows)")
    ax.hist(np.clip(attack, bins[0], bins[-1]), bins=bins, density=True, alpha=0.6, color=RED, label=f"known attacks ({len(attack):,})")
    ax.axvspan(min(thr), max(thr), color=GREY, alpha=0.25, label=f"client thresholds ({min(thr):.3f} to {max(thr):.3f})")
    ax.set_xscale("log")
    ax.set(xlabel="reconstruction error (MSE), log scale", ylabel="density",
           title="Autoencoder reconstruction error on held-out client test rows (10-client run)")
    ax.legend(frameon=False)
    save(fig, "reconstruction_error.png")


def clip_losses():
    path = ROOT / "results/clip/clip_comparison.csv"
    if not path.exists():
        print("skip clip")
        return
    rows = list(csv.DictReader(open(path)))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for label, color in (("clip 10", BLUE), ("no clip", RED)):
        sel = [r for r in rows if r["normalization"] == label]
        ax.plot([int(r["round"]) for r in sel], [float(r["mean_val_loss"]) for r in sel], color=color, lw=2, label=label)
    ax.set_yscale("log")
    ax.set(xlabel="round", ylabel="benign validation loss (log scale)", title="Per-client z-score clipping: benign validation loss")
    ax.legend(frameon=False)
    save(fig, "clip_val_loss.png")


def leak_auroc():
    path = ROOT / "results/leak/single_feature_auroc.json"
    if not path.exists():
        print("skip leak")
        return
    d = json.load(open(path))
    before, after = d["before"], d["after"]
    labels = [f"{k} (raw)" for k in before] + [f"{k}" for k in after]
    vals = list(before.values()) + list(after.values())
    colors = [RED] * len(before) + [BLUE] * len(after)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.barh(labels[::-1], vals[::-1], color=colors[::-1])
    ax.axvline(0.9, color=GREY, ls="--", lw=1)
    ax.text(0.9, -0.7, " test limit 0.9", color=GREY, fontsize=9, va="top")
    ax.set_xlim(0.4, 1.02)
    ax.set(xlabel="AUROC of the single feature, attack vs. normal",
           title="Placeholder spelling vs. label: before the fix (red) and best single features after it (blue)")
    save(fig, "leak_auroc.png")


def phase_b_timeline():
    src = ROOT / "results/journey/phase_b_live_demo_result.json"
    if not src.exists():
        print("skip phase b timeline")
        return
    stages = json.load(open(src))["journey"]["stages"]
    fig, ax = plt.subplots(figsize=(9.6, 3.6))
    for i, s in enumerate(stages):
        ax.barh(0, s["duration_s"], left=s["start_s"], color=[BLUE, ORANGE, GREY, RED, "#2E8B57", "#8E44AD"][i % 6], edgecolor="white")
        ax.text(s["start_s"] + s["duration_s"] / 2, 0.45 + 0.18 * (i % 3), f"{s['label']}\n{s['duration_s']:.2f} s", ha="center", fontsize=7.5)
    ax.set(xlabel="seconds since the demo started", yticks=[], ylim=(-0.5, 1.5), title="Phase B timeline: replay, classify, block, read back")
    save(fig, "phase_b_timeline.png")


if __name__ == "__main__":
    for fn in (trust_and_similarity, partition_heatmap, reconstruction_errors, clip_losses, leak_auroc, phase_b_timeline):
        try:
            fn()
        except Exception as exc:  # keep going; report which figure failed
            print("FAILED", fn.__name__, type(exc).__name__, exc)
