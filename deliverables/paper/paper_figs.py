"""Figures for the paper, drawn from the result files in this repository (nothing typed in by hand).

Run from the repo root in the VM:  venv/bin/python deliverables/paper/paper_figs.py
Writes vector PDFs to deliverables/paper/figs/.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/paper/figs"
OUT.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, GREEN, RED, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#6B6B6B"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
    "pdf.fonttype": 42, "figure.dpi": 150,
})
J = lambda p: json.load(open(ROOT / p))
SUM = J("results/full/summary.json")
SEEDCOL = {0: BLUE, 1: ORANGE, 2: GREEN}


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ---- Fig: false alarms counted three ways (six real runs)
tags = ["c10_s42", "c10_s43", "c10_s44", "c20_s42", "c20_s43", "c20_s44"]
labs = ["10\ns42", "10\ns43", "10\ns44", "20\ns42", "20\ns43", "20\ns44"]
fl = {t: J(f"results/full/{t}/flow_fpr/summary.json") for t in tags}
x = np.arange(len(tags)); w = 0.27
fig, ax = plt.subplots(figsize=(3.5, 2.3))
ax.bar(x - w, [fl[t]["packet_fpr"] for t in tags], w, color=RED, label="all benign packets")
ax.bar(x, [fl[t]["median_client_packet_fpr"] for t in tags], w, color=BLUE, label="median client, packets")
ax.bar(x + w, [fl[t]["flow_fpr"] for t in tags], w, color=GREEN, label="benign connections (half+ flagged)")
ax.set_xticks(x, labs)
ax.set_xlabel("clients / seed")
ax.set_ylabel("false-alarm rate")
ax.legend(frameon=False, loc="upper center", fontsize=6.3, ncol=1)
ax.set_ylim(0, 0.27)
save(fig, "fig_fa.pdf")

# ---- Fig: poisoning sweep (three seeds)
fr = ["0.0", "0.2", "0.3", "0.4", "0.5"]
xs = [0, 20, 30, 40, 50]
fig, (a, b) = plt.subplots(1, 2, figsize=(7.1, 2.3))
for s in range(3):
    a.plot(xs, [SUM["sweep"][f]["attack_macro_recall"][s] for f in fr], "-o", color=SEEDCOL[s], ms=3, lw=1, label=f"cascade, seed {42 + s}")
    a.plot(xs, [SUM["sweep"][f]["autoencoder_alone_attack_macro_recall"][s] for f in fr], "--s", color=SEEDCOL[s], ms=3, lw=1, label=f"autoencoder alone, seed {42 + s}")
    sv = [SUM["sweep"][f]["malicious_client_survival_rate"][s] for f in fr[1:]]
    b.plot(xs[1:], sv, "-o", color=SEEDCOL[s], ms=3, lw=1, label=f"seed {42 + s}")
a.set_xlabel("sign-flip attackers among clients (%)"); a.set_ylabel("attack macro-recall"); a.set_ylim(-0.02, 1.02)
a.set_title("(a) Detection under poisoning", loc="left")
a.legend(frameon=False, ncol=3, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.22))
b.set_xlabel("sign-flip attackers among clients (%)"); b.set_ylabel("attacker-rounds admitted"); b.set_ylim(0, 1.05)
b.set_title("(b) Attacker survival", loc="left"); b.legend(frameon=False, fontsize=6.5)
fig.tight_layout()
save(fig, "fig_poison.pdf")

# ---- Fig: zero-day dot plot
cls = list(SUM["zero_day_class"].keys())
cas = {c: np.array(SUM["zero_day_class"][c]["cascade_detection_rate"]) for c in cls}
order = sorted(cls, key=lambda c: cas[c].mean())
fig, ax = plt.subplots(figsize=(3.5, 3.4))
for i, c in enumerate(order):
    for key, col, m, dy in (("boosting_only_detection_rate", BLUE, "o", 0.22), ("autoencoder_alone_detection_rate", ORANGE, "s", 0.0), ("cascade_detection_rate", GREEN, "D", -0.22)):
        v = np.array(SUM["zero_day_class"][c][key])
        ax.plot([v.min(), v.max()], [i + dy] * 2, color=col, lw=0.8)
        ax.plot(v.mean(), i + dy, m, color=col, ms=3.2)
ax.set_yticks(range(len(order)), [c.replace("_", " ") for c in order])
ax.set_xlabel("detection rate of the held-out class (marker: mean of 3 seeds; line: range)")
ax.xaxis.label.set_size(6.5)
ax.set_xlim(-0.02, 1.02)
for key, col, m, name in (("b", BLUE, "o", "classifier alone"), ("a", ORANGE, "s", "autoencoder alone"), ("c", GREEN, "D", "cascade")):
    ax.plot([], [], m, color=col, ms=3.2, label=name)
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, fontsize=6.3)
save(fig, "fig_zeroday.pdf")

# ---- Fig: per-class F1, base vs final
base = J("experiments/accuracy/results/base_grouped_s42.json")
fin = J("experiments/accuracy/results/full_grouped_bal_s42.json")
names = [c for c in fin["classes"] if c != "MITM"]
f1b = {c: base["per_class"][c]["f1-score"] for c in names}
f1f = {c: fin["per_class"][c]["f1-score"] for c in names}
names = sorted(names, key=lambda c: f1b[c])
fig, ax = plt.subplots(figsize=(3.5, 3.0))
y = np.arange(len(names))
ax.barh(y + 0.19, [f1b[c] for c in names], 0.36, color=GREY, label="91 base features")
ax.barh(y - 0.19, [f1f[c] for c in names], 0.36, color=BLUE, label="130 features + class weights")
ax.set_yticks(y, [c.replace("_", " ") for c in names])
ax.set_xlim(0.6, 1.0)
ax.set_xlabel("per-class F1, connection-grouped test split (seed 42)")
ax.xaxis.label.set_size(6.8)
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, fontsize=6.3)
save(fig, "fig_f1.pdf")

# ---- Fig: confusion matrix of the final classifier (row-normalised, 14 classes scored)
cm = np.array(fin["confusion_matrix"], dtype=float)
keep = [i for i in range(len(fin["classes"])) if cm[i].sum() > 0]
cm = cm[np.ix_(keep, keep)]
nm = [fin["classes"][i].replace("_", " ").replace("Vulnerability scanner", "Vuln. scanner").replace("Fingerprinting", "Fingerprint.") for i in keep]
nrm = cm / cm.sum(axis=1, keepdims=True)
cmap = LinearSegmentedColormap.from_list("b", ["#FFFFFF", "#DCE9F7", "#8FB8E3", "#2E75B6", "#1F3864"])
fig, ax = plt.subplots(figsize=(3.5, 3.3))
ax.imshow(nrm, cmap=cmap, norm=PowerNorm(gamma=0.5, vmin=0, vmax=1))
for i in range(len(nm)):
    for j in range(len(nm)):
        v = nrm[i, j]
        if v >= 0.005:
            ax.text(j, i, "1" if v >= 0.995 else f"{v:.2f}".lstrip("0"), ha="center", va="center", fontsize=4.6, color="white" if v > 0.5 else "#222")
ax.set_xticks(range(len(nm)), nm, rotation=60, ha="right", fontsize=5.5)
ax.set_yticks(range(len(nm)), nm, fontsize=5.5)
ax.set_xlabel("predicted class"); ax.set_ylabel("true class")
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
save(fig, "fig_cm.pdf")
print("acc from matrix", np.trace(cm) / cm.sum(), "classes", len(nm))
