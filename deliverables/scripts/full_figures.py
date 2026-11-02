"""Figures for the full-pool (connection-grouped) results. Reads results/full/ and results/real_runs/, results/seeds/summary.json.

Run from the repo root in the VM:  venv/bin/python deliverables/scripts/full_figures.py
Writes deliverables/report/figures/full_pool_runs.png and full_zero_day.png.
"""
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
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
TAGS = ["c10_s42", "c10_s43", "c10_s44", "c20_s42", "c20_s43", "c20_s44"]
LABELS = ["10 cl.\nseed 42", "10 cl.\nseed 43", "10 cl.\nseed 44", "20 cl.\nseed 42", "20 cl.\nseed 43", "20 cl.\nseed 44"]


def load(path):
    return json.load(open(path))


old = {t: load(ROOT / f"results/real_runs/{t}/summary.json")["cascade"] for t in TAGS}
new = {t: load(ROOT / f"results/full/{t}/breakdown/summary.json")["cascade"] for t in TAGS}
flow = {t: load(ROOT / f"results/full/{t}/flow_fpr/summary.json") for t in TAGS}
x = np.arange(len(TAGS))

fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4))
w = 0.38
a.bar(x - w / 2, [old[t]["attack_micro_recall"] for t in TAGS], w, color=GREY, label="earlier: 60k pool, split by row")
a.bar(x + w / 2, [new[t]["attack_micro_recall"] for t in TAGS], w, color=BLUE, label="now: full pool, split by connection")
a.set_ylim(0.99, 1.0005)
a.set_xticks(x)
a.set_xticklabels(LABELS, fontsize=9)
a.set(ylabel="attack packets caught (micro recall)", title="Catching attacks (axis starts at 0.99)")
a.legend(frameon=False, fontsize=9, loc="lower right")
w = 0.27
b.bar(x - w, [old[t]["benign_fpr"] * 100 for t in TAGS], w, color=GREY, label="earlier, packets (60k pool, by row)")
b.bar(x, [new[t]["benign_fpr"] * 100 for t in TAGS], w, color=ORANGE, label="now, packets (full pool)")
b.bar(x + w, [flow[t]["flow_fpr"] * 100 for t in TAGS], w, color=BLUE, label="now, connections (full pool)")
b.set_xticks(x)
b.set_xticklabels(LABELS, fontsize=9)
b.set(ylabel="normal traffic wrongly flagged (%)", title="False alarms: packets vs. connections")
b.legend(frameon=False, fontsize=9)
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "full_pool_runs.png", dpi=160, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("wrote full_pool_runs.png")

# zero-day per class: full pool (three seeds) vs the earlier 60k mean
s60 = load(ROOT / "results/seeds/summary.json")["zero_day_cascade"]
full = load(ROOT / "results/full/summary.json")["zero_day_class"]
classes = sorted(full)
fig, ax = plt.subplots(figsize=(10.5, 4.6))
for i, c in enumerate(classes):
    vals = full[c]["cascade_detection_rate"]
    ax.scatter([i] * len(vals), vals, color=BLUE, s=22, zorder=3, label="full pool, one dot per seed" if i == 0 else None)
    ax.scatter([i], [np.mean(s60[c])], marker="_", s=260, color=GREY, linewidths=2.4, zorder=2, label="earlier 60k pool, mean of 3 seeds" if i == 0 else None)
ax.set_xticks(range(len(classes)))
ax.set_xticklabels(classes, rotation=55, ha="right")
ax.set(ylabel="share of the unseen attack type detected", ylim=(0.45, 1.02), title="Zero-day detection by the cascade, one attack type held out at a time")
ax.legend(frameon=False, loc="lower left", fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "full_zero_day.png", dpi=160, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("wrote full_zero_day.png")
