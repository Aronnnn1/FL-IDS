"""Merge and summarise the full-pool (connection-grouped) experiments.

Reads the job outputs written by tools/run_full_experiments.py (results/full/inprocess/s<seed>/shards/), the real multi-process
runs (runs/full/<tag>/, results/full/<tag>/breakdown/, logs/full/<tag>/) and writes:
  results/full/inprocess/s<seed>/{poisoning_resistance_sweep,zero_day_holdout,ablation_table,stealth,pruning_fl,noclip}.csv
  results/full/summary.{json,md}   (all tables, three seeds side by side)
    python3 tools/summarize_full.py
"""
import csv
import glob
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "results/full"
SEEDS = (42, 43, 44)


def read(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))


def fl(v):
    return float(v) if v not in ("", None) else float("nan")


def write(path, rows):
    if rows:
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def shard_rows(seed, pattern, fname):
    rows = []
    for d in sorted(glob.glob(str(FULL / f"inprocess/s{seed}/shards/{pattern}"))):
        if (Path(d) / ".done").exists() and (Path(d) / fname).is_file():
            rows += read(Path(d) / fname)
    return rows


def triple(vals, d=3):
    return " / ".join("n/a" if v != v else f"{v:.{d}f}" for v in vals)


merged = {}
for s in SEEDS:
    out = FULL / f"inprocess/s{s}"
    sweep = shard_rows(s, f"sweep_s{s}_f*", "poisoning_resistance_sweep.csv")
    zd = shard_rows(s, f"zeroday_s{s}_*", "zero_day_holdout.csv")
    abl = shard_rows(s, f"ablation_s{s}_*", "ablation_table.csv")
    f30 = [r for r in sweep if abs(fl(r["malicious_fraction"]) - 0.3) < 1e-9]
    if f30 and abl:  # the full-pipeline row of the ablation is the sweep's 30% point (same data, seed, attackers)
        cols = list(abl[0].keys())
        abl = [{**{c: f30[0].get(c, "") for c in cols}, "variant": "full_pipeline"}] + abl
    stealth = shard_rows(s, f"stealth_s{s}_*", "adaptive_attack.csv")
    prune = shard_rows(s, f"prunefl_s{s}_*", "pruning_during_fl.csv")
    f00 = [r for r in sweep if abs(fl(r["malicious_fraction"])) < 1e-9]
    noclip = shard_rows(s, f"noclip_s{s}", "clip_comparison.csv")
    for name, rows in (("poisoning_resistance_sweep", sweep), ("zero_day_holdout", zd), ("ablation_table", abl), ("stealth", stealth),
                       ("pruning_fl", prune), ("noclip", noclip)):
        write(out / f"{name}.csv", rows)
    merged[s] = dict(sweep=sweep, zd=zd, abl=abl, stealth=stealth, prune=prune, f00=f00, noclip=noclip)

md, js = [], {}
have = [s for s in SEEDS if merged[s]["sweep"]]

md += ["### Ablation at 30% sign-flip attackers, full pool, seeds " + " / ".join(map(str, have)), "",
       "| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR |", "|---|---|---|---|"]
variants = [r["variant"] for r in merged[have[0]]["abl"]] if have and merged[have[0]]["abl"] else []
for v in variants:
    rows = [next((r for r in merged[s]["abl"] if r["variant"] == v), None) for s in have]
    g = lambda c: [fl(r[c]) if r else float("nan") for r in rows]  # noqa: E731
    md.append(f"| {v} | {triple(g('attack_macro_recall'))} | {triple(g('autoencoder_alone_attack_macro_recall'))} | {triple(g('benign_fpr'), 4)} |")
    js.setdefault("ablation", {})[v] = {c: g(c) for c in ("attack_macro_recall", "autoencoder_alone_attack_macro_recall", "benign_fpr", "final_val_loss")}

md += ["", "### Poisoning sweep, full pool", "", "| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |", "|---|---|---|---|"]
for frac in (0.0, 0.2, 0.3, 0.4, 0.5):
    rows = [next((r for r in merged[s]["sweep"] if abs(fl(r["malicious_fraction"]) - frac) < 1e-9), None) for s in have]
    g = lambda c: [fl(r[c]) if r else float("nan") for r in rows]  # noqa: E731
    md.append(f"| {frac:.0%} | {triple(g('attack_macro_recall'))} | {triple(g('autoencoder_alone_attack_macro_recall'))} | {triple(g('malicious_client_survival_rate'), 2)} |")
    js.setdefault("sweep", {})[str(frac)] = {c: g(c) for c in ("attack_macro_recall", "attack_micro_recall", "autoencoder_alone_attack_macro_recall", "malicious_client_survival_rate", "benign_fpr", "final_val_loss")}

md += ["", "### Zero-day (leave one attack class out), full pool: mean over the held-out classes", "", "| Stage | Mean detection rate |", "|---|---|"]
for label, col in (("Classifier alone", "boosting_only_detection_rate"), ("Autoencoder alone", "autoencoder_alone_detection_rate"), ("Cascade", "cascade_detection_rate")):
    means = [st.mean(fl(r[col]) for r in merged[s]["zd"]) if merged[s]["zd"] else float("nan") for s in have]
    md.append(f"| {label} | {triple(means)} (classes: {', '.join(str(len(merged[s]['zd'])) for s in have)}) |")
    js.setdefault("zero_day_mean", {})[label] = means
md += ["", "| Held-out class | Rows scored | Cascade detection | Classifier alone | Autoencoder alone |", "|---|---|---|---|---|"]
classes = sorted({r["holdout_class"] for s in have for r in merged[s]["zd"]})
for c in classes:
    rows = [next((r for r in merged[s]["zd"] if r["holdout_class"] == c), None) for s in have]
    g = lambda col: [fl(r[col]) if r else float("nan") for r in rows]  # noqa: E731
    n = next((r["holdout_rows"] for r in rows if r), "")
    md.append(f"| {c} | {n} | {triple(g('cascade_detection_rate'))} | {triple(g('boosting_only_detection_rate'))} | {triple(g('autoencoder_alone_detection_rate'))} |")
    js.setdefault("zero_day_class", {})[c] = {k: g(k) for k in ("cascade_detection_rate", "boosting_only_detection_rate", "autoencoder_alone_detection_rate")}

md += ["", "### Stealth attacker vs. sign-flip, full pool", "", "| Attackers | Sign-flip survival | Stealth survival | Sign-flip AE-alone recall | Stealth AE-alone recall | Stealth known-attack recall |", "|---|---|---|---|---|---|"]
for frac in (0.2, 0.3, 0.4):
    sf = [next((r for r in merged[s]["sweep"] if abs(fl(r["malicious_fraction"]) - frac) < 1e-9), None) for s in have]
    sl = [next((r for r in merged[s]["stealth"] if abs(fl(r["malicious_fraction"]) - frac) < 1e-9), None) for s in have]
    g = lambda rows, c: [fl(r[c]) if r else float("nan") for r in rows]  # noqa: E731
    md.append(f"| {frac:.0%} | {triple(g(sf, 'malicious_client_survival_rate'), 2)} | {triple(g(sl, 'malicious_client_survival_rate'), 2)} | "
              f"{triple(g(sf, 'autoencoder_alone_attack_macro_recall'))} | {triple(g(sl, 'autoencoder_alone_attack_macro_recall'))} | {triple(g(sl, 'attack_macro_recall'), 4)} |")
    js.setdefault("stealth", {})[str(frac)] = {"sign_flip_survival": g(sf, "malicious_client_survival_rate"), "stealth_survival": g(sl, "malicious_client_survival_rate"),
                                              "stealth_ae_recall": g(sl, "autoencoder_alone_attack_macro_recall"), "sign_flip_ae_recall": g(sf, "autoencoder_alone_attack_macro_recall")}

md += ["", "### Pruning during federated training, full pool (no attackers)", "", "| Sparsity | Non-zero weights | Autoencoder-alone recall | Cascade macro-recall | Benign FPR |", "|---|---|---|---|---|"]
for sp in (0.0, 0.5, 0.7, 0.8, 0.9):
    cells = []
    for s in have:
        src = merged[s]["f00"] if sp == 0.0 else merged[s]["prune"]
        r = next((x for x in src if abs(fl(x.get("sparsity", 0.0)) - sp) < 1e-9), None) if sp else (src[0] if src else None)
        cells.append(r)
    ae = [fl(r["autoencoder_alone_attack_macro_recall"]) if r else float("nan") for r in cells]
    cm = [fl(r["attack_macro_recall"]) if r else float("nan") for r in cells]
    fp = [fl(r["benign_fpr"]) if r else float("nan") for r in cells]
    nz = next((r["nonzero_weights"] for r in cells if r and r.get("nonzero_weights")), "9600" if sp == 0 else "")
    md.append(f"| {sp:.0%} | {nz} | {triple(ae)} | {triple(cm)} | {triple(fp, 4)} |")
    js.setdefault("pruning", {})[str(sp)] = {"ae_recall": ae, "cascade_macro": cm, "fpr": fp}

md += ["", "### Per-client z-score clip, final-round benign validation loss", "", "| Normalisation | " + " | ".join(f"seed {s}" for s in have) + " |", "|---|" + "---|" * len(have)]
for label, src in (("clip 10", "f00"), ("no clip", "noclip")):
    cells = []
    for s in have:
        if src == "f00":
            r = merged[s]["f00"]
            cells.append(f"{fl(r[0]['final_val_loss']):.4g}" if r else "n/a")
        else:
            rows = [x for x in merged[s]["noclip"] if int(x["round"]) == 20]
            cells.append(f"{fl(rows[0]['mean_val_loss']):.4g}" if rows else "n/a")
    md.append(f"| {label} | " + " | ".join(cells) + " |")

# real multi-process runs
md += ["", "### Real multi-process Phase A, full pool, split by connection", "",
       "| Run | Phase A s | Attack macro-recall | Attack micro recall | Boosting-only micro recall | Benign FPR | Test rows | Clients with infinite threshold |", "|---|---|---|---|---|---|---|---|"]
real = []
for tag in sorted(p.name for p in (ROOT / "runs/full").glob("c*_s*")) if (ROOT / "runs/full").exists() else []:
    bd = FULL / tag / "breakdown"
    log = ROOT / f"logs/full/{tag}/phase_a.log"
    if not (bd / "summary.json").exists() or not log.exists():
        continue
    m = re.search(r"Phase A done in ([\d.]+)s", log.read_text())
    sm = json.load(open(bd / "summary.json"))
    pcl = read(bd / "per_client.csv")
    n_test = sum(int(r["test_rows"]) for r in pcl)
    inf = sum(r["threshold_infinite"] == "True" for r in pcl)
    row = dict(run=tag, seconds=float(m.group(1)) if m else None, macro=sm["cascade"]["attack_macro_recall"], micro=sm["cascade"]["attack_micro_recall"],
               boost_micro=sm["boosting_only"]["attack_micro_recall"], fpr=sm["cascade"]["benign_fpr"], test_rows=n_test, inf=inf)
    real.append(row)
    md.append(f"| {tag.replace('c', '').replace('_s', ' clients, seed ')} | {row['seconds']:.0f} | {row['macro']:.4f} | {row['micro']:.4f} | {row['boost_micro']:.4f} | {row['fpr']:.4f} | {n_test:,} | {inf} |")
js["real_runs"] = real

(FULL / "summary.md").write_text("\n".join(md) + "\n")
(FULL / "summary.json").write_text(json.dumps(js, indent=1, default=str))
print("\n".join(md))
