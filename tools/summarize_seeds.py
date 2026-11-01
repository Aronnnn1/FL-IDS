"""Summarise the ablation, poisoning sweep and zero-day experiments across seeds 42 (results/extended), 43 and 44.

Reads the CSVs the experiments wrote; writes results/seeds/summary.md and summary.json. Zero-day columns inside the
ablation and sweep tables were run for seed 42 only; the standalone zero-day experiment is repeated for all three seeds.
    python3 tools/summarize_seeds.py
"""
import csv
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = {42: ROOT / "results/extended", 43: ROOT / "results/seeds/s43", 44: ROOT / "results/seeds/s44"}


def rows(seed, name):
    with open(DIRS[seed] / name) as fh:
        return list(csv.DictReader(fh))


def f(v):
    return float(v) if v not in ("", None) else float("nan")


def cell(vals, digits=3, pct=False):
    vals = [v for v in vals if v == v]
    if not vals:
        return "n/a"
    scale = 100 if pct else 1
    body = " / ".join(f"{scale * v:.{digits}f}" for v in vals)
    return f"{body} (mean {scale * st.mean(vals):.{digits}f})"


out, summary = [], {}

# ablation
out += ["### Ablation (30% sign-flip attackers, 20 rounds): seeds 42 / 43 / 44", "",
        "| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR | Final validation loss |", "|---|---|---|---|---|"]
by = {s: {r["variant"]: r for r in rows(s, "ablation_table.csv")} for s in DIRS}
for variant in by[42]:
    g = lambda col: [f(by[s][variant][col]) for s in DIRS]  # noqa: E731
    loss = [f"{v:.3g}" if v == v else "n/a" for v in g("final_val_loss")]
    out.append(f"| {variant} | {cell(g('attack_macro_recall'))} | {cell(g('autoencoder_alone_attack_macro_recall'))} | "
               f"{cell(g('benign_fpr'), 4)} | {' / '.join(loss)} |")
    summary.setdefault("ablation", {})[variant] = {c: g(c) for c in ("attack_macro_recall", "autoencoder_alone_attack_macro_recall", "benign_fpr", "final_val_loss")}

# sweep
out += ["", "### Poisoning sweep (full pipeline): seeds 42 / 43 / 44", "",
        "| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |", "|---|---|---|---|"]
sw = {s: {r["malicious_fraction"]: r for r in rows(s, "poisoning_resistance_sweep.csv")} for s in DIRS}
for frac in sw[42]:
    g = lambda col: [f(sw[s][frac][col]) for s in DIRS if frac in sw[s]]  # noqa: E731
    out.append(f"| {float(frac):.0%} | {cell(g('attack_macro_recall'))} | {cell(g('autoencoder_alone_attack_macro_recall'))} | {cell(g('malicious_client_survival_rate'), 2)} |")
    summary.setdefault("sweep", {})[frac] = {c: g(c) for c in ("attack_macro_recall", "autoencoder_alone_attack_macro_recall", "malicious_client_survival_rate")}

# zero-day
out += ["", "### Zero-day (leave one attack class out): mean over the 14 classes, seeds 42 / 43 / 44", "",
        "| Stage | Mean detection rate of the unseen class |", "|---|---|"]
zd = {s: rows(s, "zero_day_holdout.csv") for s in DIRS}
for label, col in (("Classifier alone", "boosting_only_detection_rate"), ("Autoencoder alone", "autoencoder_alone_detection_rate"), ("Cascade", "cascade_detection_rate")):
    means = [st.mean(f(r[col]) for r in zd[s]) for s in DIRS]
    out.append(f"| {label} | {cell(means)} |")
    summary.setdefault("zero_day_mean", {})[label] = means
out += ["", "| Held-out class | Cascade detection, seed 42 / 43 / 44 |", "|---|---|"]
classes = [r["holdout_class"] for r in zd[42]]
for c in classes:
    vals = [f(next(r for r in zd[s] if r["holdout_class"] == c)["cascade_detection_rate"]) for s in DIRS]
    out.append(f"| {c} | {' / '.join(f'{v:.3f}' for v in vals)} |")
    summary.setdefault("zero_day_cascade", {})[c] = vals

p = ROOT / "results/seeds"
(p / "summary.md").write_text("\n".join(out) + "\n")
(p / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
print("\n".join(out))
