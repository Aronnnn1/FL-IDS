"""Build the follow-up experiment tables (markdown for PAPER_NOTES, LaTeX for the report, HTML for the results page).

Every cell is read from a result file written by the experiment itself. Output: results/followups/{tables.json,
tables.md, tables.tex, tables.html}. Run from the repo root after the experiments:  python3 tools/build_followups.py
"""
import csv
import glob
import html
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/followups"
OUT.mkdir(parents=True, exist_ok=True)


def rd(path):
    with open(ROOT / path) as fh:
        return list(csv.DictReader(fh))


def fl(v):
    return float(v) if v not in ("", None) else float("nan")


def three(vals, d=3):
    return " / ".join("n/a" if v != v else f"{v:.{d}f}" for v in vals)


TABLES = {}  # key -> (caption, header, rows)

# 1. seeds -----------------------------------------------------------------------------------------------------------
S = json.load(open(ROOT / "results/seeds/summary.json"))
TABLES["seed_ablation"] = (
    "Ablation at 30% sign-flip attackers, seeds 42 / 43 / 44 (source: results/seeds/summary.json)",
    ["Variant", "Attack macro-recall", "Autoencoder-alone recall", "Benign FPR"],
    [[v, three(d["attack_macro_recall"]), three(d["autoencoder_alone_attack_macro_recall"]), three(d["benign_fpr"], 4)]
     for v, d in S["ablation"].items()],
)
TABLES["seed_sweep"] = (
    "Poisoning sweep, seeds 42 / 43 / 44",
    ["Attackers", "Attack macro-recall", "Autoencoder-alone recall", "Attacker survival"],
    [[f"{float(k):.0%}", three(d["attack_macro_recall"]), three(d["autoencoder_alone_attack_macro_recall"]),
      three(d["malicious_client_survival_rate"], 2)] for k, d in S["sweep"].items()],
)
TABLES["seed_zeroday"] = (
    "Zero-day detection of the unseen class, mean over 14 classes, seeds 42 / 43 / 44",
    ["Stage", "Mean detection rate"],
    [[k, three(v)] for k, v in S["zero_day_mean"].items()]
    + [[f"Cascade, {c}", three(v)] for c, v in S["zero_day_cascade"].items() if c in ("MITM", "Uploading", "DDoS_HTTP")],
)

# 2. adaptive attacker -----------------------------------------------------------------------------------------------
A = rd("results/adaptive/adaptive_attack.csv")
TABLES["adaptive"] = (
    "Adaptive (stealth) attacker vs. sign-flip, seed 42, 20 rounds (source: results/adaptive/adaptive_attack.csv)",
    ["Attack", "Attackers", "Attack macro-recall", "Autoencoder-alone recall", "Attacker survival", "Final validation loss"],
    [[r["attack"], f"{float(r['malicious_fraction']):.0%}", f"{fl(r['attack_macro_recall']):.4f}",
      f"{fl(r['autoencoder_alone_attack_macro_recall']):.3f}", f"{fl(r['malicious_client_survival_rate']):.2f}",
      f"{fl(r['final_val_loss']):.3f}"] for r in A],
)

# 3. pruning ---------------------------------------------------------------------------------------------------------
P1 = rd("results/pruning/c10_s42/pruning.csv")
P2 = rd("results/pruning/pruning_during_fl.csv")
TABLES["prune_post"] = (
    "Post-training magnitude pruning of the 10-client autoencoder, thresholds recalibrated (source: results/pruning/c10_s42/pruning.csv)",
    ["Sparsity", "Non-zero weights", "Sparse / dense bytes", "Autoencoder recall", "Autoencoder AUROC", "Cascade macro-recall", "Benign FPR"],
    [[f"{fl(r['sparsity']):.0%}", r["nonzero_weights"], f"{fl(r['sparse_vs_dense_bytes']):.2f}", f"{fl(r['ae_attack_macro_recall']):.3f}",
      f"{fl(r['ae_auroc']):.3f}", f"{fl(r['cascade_attack_macro_recall']):.3f}", f"{fl(r['benign_fpr']):.4f}"] for r in P1],
)
TABLES["prune_fl"] = (
    "Pruning during federated training (server re-prunes each round, linear ramp over the first 10 rounds), seed 42, no attackers (source: results/pruning/pruning_during_fl.csv)",
    ["Sparsity", "Non-zero weights", "Sparse / dense bytes", "Autoencoder-alone recall", "Cascade macro-recall", "Benign FPR", "Final validation loss"],
    [[f"{fl(r['sparsity']):.0%}", r["nonzero_weights"], f"{fl(r['sparse_bytes']) / fl(r['dense_bytes']):.2f}",
      f"{fl(r['autoencoder_alone_attack_macro_recall']):.3f}", f"{fl(r['attack_macro_recall']):.3f}", f"{fl(r['benign_fpr']):.4f}",
      f"{fl(r['final_val_loss']):.3f}"] for r in P2],
)

# 4. clipping --------------------------------------------------------------------------------------------------------
C = rd("results/clip/clip_comparison.csv")
rounds = (1, 5, 10, 20)
TABLES["clip"] = (
    "Benign validation loss with and without the per-client z-score clip (source: results/clip/clip_comparison.csv)",
    ["Normalisation"] + [f"Round {n}" for n in rounds],
    [[lab] + [f"{fl(next(r['mean_val_loss'] for r in C if r['normalization'] == lab and int(r['round']) == n)):.4g}" for n in rounds]
     for lab in ("clip 10", "no clip")],
)

# 5. time-ordered split ----------------------------------------------------------------------------------------------
T = {s: json.load(open(ROOT / f"experiments/accuracy/results/full_temporal_bal_s{s}.json")) for s in (42, 43, 44)}
G = json.load(open(ROOT / "experiments/accuracy/results/full_grouped_bal_s42.json"))
TABLES["temporal_summary"] = (
    "Per-class time-ordered split vs. connection-grouped split (source: experiments/accuracy/results/full_temporal_bal_s*.json)",
    ["Split", "Accuracy", "Macro F1"],
    [["Time-ordered, seeds 42 / 43 / 44", three([T[s]["accuracy"] for s in T], 4), three([T[s]["macro_f1"] for s in T], 4)],
     ["Connection-grouped, seed 42", f"{G['accuracy']:.4f}", f"{G['macro_f1']:.4f}"]],
)
TABLES["temporal_classes"] = (
    "Recall per class, time-ordered split (seeds 42 / 43 / 44) vs. grouped split (seed 42)",
    ["Class", "Test rows (time-ordered)", "Time-ordered recall", "Grouped recall"],
    [[c, int(T[42]["per_class"][c]["support"]), three([T[s]["per_class"][c]["recall"] for s in T]), f"{G['per_class'][c]['recall']:.3f}"]
     for c in T[42]["classes"]],
)

# 6. placeholder leak ------------------------------------------------------------------------------------------------
L = json.load(open(ROOT / "results/leak/single_feature_auroc.json"))
TABLES["leak"] = (
    f"Single-feature AUROC, attack vs. normal (source: results/leak/single_feature_auroc.json; after: {L['sample_rows']:,}-row sample)",
    ["Feature", "AUROC", "State"],
    [[k, f"{v:.4f}", "raw, before the fix"] for k, v in L["before"].items()] + [[k, f"{v:.4f}", "130-feature matrix, after"] for k, v in L["after"].items()],
)

# 7. real-run breakdown ----------------------------------------------------------------------------------------------
rows7 = []
for d in sorted(glob.glob(str(ROOT / "results/real_runs/c*_s*"))):
    name = Path(d).name
    s = json.load(open(f"{d}/summary.json"))["cascade"]
    pc = {r["class"]: r for r in rd(f"results/real_runs/{name}/per_class_recall.csv")}
    inf = sum(r["threshold_infinite"] == "True" for r in rd(f"results/real_runs/{name}/per_client.csv"))
    fp, mi = pc["Fingerprinting"], pc["MITM"]
    rows7.append([name.replace("c", "").replace("_s", " clients, seed "), f"{s['attack_macro_recall']:.3f}", f"{s['attack_micro_recall']:.4f}",
                  f"{fp['test_rows']} rows, {fl(fp['cascade']):.2f}", f"{mi['test_rows']} rows, {fl(mi['cascade']):.2f}", str(inf)])
TABLES["realrun_breakdown"] = (
    "Where the real-run macro-recall comes from (source: results/real_runs/<run>/, made by fl_ids.eval.bundle_report)",
    ["Run", "Macro-recall", "Micro recall", "Fingerprinting test rows, recall", "MITM test rows, recall", "Clients with infinite threshold"],
    rows7,
)

# 8. real runs with attackers ----------------------------------------------------------------------------------------
rows8 = []
for run, lab in (("mal02", "20%"), ("mal03", "30%")):
    man = json.load(open(ROOT / f"saved_models/attack_runs/{run}/manifest.json"))["training"]
    hist = json.load(open(ROOT / f"runs/attack_runs/{run}/history.json"))["round_history"]
    bad = {str(c) for c in man["malicious_client_ids"]}
    good = [c for c in hist[0]["trust_scores"] if c not in bad]
    ex = sum(1 for h in hist for c in bad if c in h.get("exclusion_reasons", {}))
    hx = sum(1 for h in hist for c in good if c in h.get("exclusion_reasons", {}))
    log = (ROOT / f"logs/attack_runs/{run}.log").read_text()
    m = re.search(r"cascade attack macro-recall ([\d.]+), benign FPR ([\d.]+)", log)
    rows8.append([lab, ",".join(sorted(bad, key=int)), f"{ex} of {len(hist) * len(bad)}", f"{hx} of {len(hist) * len(good)}", m.group(1), m.group(2)])
TABLES["attack_runs"] = (
    "Real multi-process Phase A with sign-flip attackers (10 clients, 20 rounds, seed 42; source: runs/attack_runs/)",
    ["Attackers", "Attacker clients", "Attacker client-rounds excluded", "Honest client-rounds excluded", "Attack macro-recall", "Benign FPR"],
    rows8,
)

# 9. Phase B on the seed bundles -------------------------------------------------------------------------------------
rows9 = []
for line in (ROOT / "logs/multiseed/status_phase_b.log").read_text().splitlines():
    m = re.match(r"(c\d+_s\d+) phase_b (\w+) Phase B done in ([\d.]+)s: .*?-> (\w+) \(confidence ([\d.]+), (\w+) stage, (\d+)/(\d+) packets", line)
    if m:
        rows9.append([m.group(1).replace("c", "").replace("_s", " clients, seed "), m.group(4), m.group(5), f"{m.group(7)} / {m.group(8)}", m.group(3) + " s"])
TABLES["phase_b_seeds"] = (
    "Phase B on the multi-seed bundles, Backdoor_attack.pcap, every run ends with a drop rule read back from the switch (source: logs/multiseed/status_phase_b.log)",
    ["Bundle", "Class", "Confidence", "Packets flagged", "Phase B time"],
    rows9,
)

json.dump({k: {"caption": c, "header": h, "rows": r} for k, (c, h, r) in TABLES.items()}, open(OUT / "tables.json", "w"), indent=1)


def md(key):
    c, h, r = TABLES[key]
    return f"**{c}**\n\n| " + " | ".join(h) + " |\n|" + "---|" * len(h) + "\n" + "\n".join("| " + " | ".join(str(x) for x in row) + " |" for row in r) + "\n"


def tex(key, label):
    c, h, r = TABLES[key]
    esc = lambda s: str(s).replace("\\", "").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")  # noqa: E731
    cols = "|" + "l|" + "c|" * (len(h) - 1)
    body = "\n".join(" & ".join(esc(x) for x in row) + r" \\ \hline" for row in r)
    head = " & ".join(r"\textbf{" + esc(x) + "}" for x in h)
    size = "\\scriptsize" if len(h) >= 5 else "\\small"
    return (f"\\begin{{table}}[H]\n\\centering\n{size}\n\\setlength{{\\tabcolsep}}{{3pt}}\n\\renewcommand{{\\arraystretch}}{{1.15}}\n\\begin{{tabular}}{{{cols}}}\n\\hline\n{head} \\\\ \\hline\n"
            f"{body}\n\\end{{tabular}}\n\\caption{{{esc(c)}}}\n\\label{{tab:{label}}}\n\\end{{table}}\n")


def htm(key):
    c, h, r = TABLES[key]
    e = html.escape
    return (f"<p class=\"src\"><b>{e(c)}</b></p>\n<div class=\"table-wrap\"><table class=\"ptable\">\n<thead><tr>" + "".join(f"<th>{e(x)}</th>" for x in h)
            + "</tr></thead>\n<tbody>\n" + "\n".join("<tr>" + "".join(f"<td>{e(str(x))}</td>" for x in row) + "</tr>" for row in r) + "\n</tbody></table></div>\n")


(OUT / "tables.md").write_text("\n".join(md(k) for k in TABLES))
(OUT / "tables.tex").write_text("\n".join(tex(k, "fu_" + k) for k in TABLES))
(OUT / "tables.html").write_text("\n".join(f"<!-- {k} -->\n{htm(k)}" for k in TABLES))
print("\n".join(md(k) for k in TABLES))
