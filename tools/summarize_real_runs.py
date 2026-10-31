"""Summarise real multi-process Phase A runs into results/real_runs/summary.{json,md}.

Every number is read from a run directory (journey.json, boosting_metrics.json,
history.json) or from the "Phase A done" line in its log; nothing is typed in.
    python3 tools/summarize_real_runs.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = [  # label, run dir, log
    ("10 clients, seed 42 (VM re-check)", "runs/vmware_check/phase_a", "logs/vmware_check/phase_a.log"),
    ("10 clients, seed 43", "runs/multiseed/c10_s43", "logs/multiseed/c10_s43.log"),
    ("10 clients, seed 44", "runs/multiseed/c10_s44", "logs/multiseed/c10_s44.log"),
    ("20 clients, seed 42", "runs/clients20_real/phase_a", "logs/clients20_real/phase_a.log"),
    ("20 clients, seed 43", "runs/multiseed/c20_s43", "logs/multiseed/c20_s43.log"),
    ("20 clients, seed 44", "runs/multiseed/c20_s44", "logs/multiseed/c20_s44.log"),
]
DONE = re.compile(r"Phase A done in ([\d.]+)s: cascade attack macro-recall ([\d.]+), benign FPR ([\d.]+) on (\d+) clients")


def summarise(label, run_dir, log):
    run, logp = ROOT / run_dir, ROOT / log
    if not logp.exists():
        return None
    m = DONE.search(logp.read_text())
    if not m or not (run / "journey.json").exists():
        return None
    journey = json.load(open(run / "journey.json"))
    stages = {s["label"]: s["duration_s"] for s in journey["stages"]}
    boost = json.load(open(run / "boosting_metrics.json"))
    rounds = json.load(open(run / "history.json"))["round_history"]
    excluded = [len(r.get("exclusion_reasons", {})) for r in rounds]
    return {
        "run": label, "run_dir": run_dir, "clients": int(m.group(4)),
        "total_s": float(m.group(1)), "training_s": round(stages["Federated training"], 1),
        "attack_macro_recall": float(m.group(2)), "benign_fpr": float(m.group(3)),
        "boosting_accuracy": round(boost["accuracy"], 4), "boosting_macro_f1": round(boost["macro_f1"], 4),
        "rounds": len(rounds), "clients_excluded_by_filter_total": sum(excluded),
    }


rows = [r for r in (summarise(*x) for x in RUNS) if r]
out = ROOT / "results" / "real_runs"
out.mkdir(parents=True, exist_ok=True)
(out / "summary.json").write_text(json.dumps(rows, indent=2))
md = [
    "| Run | Clients | Total s | Training s | Attack macro-recall | Benign FPR | Boosting acc / macro F1 | Filter exclusions |",
    "|---|---|---|---|---|---|---|---|",
]
for r in rows:
    md.append(
        f"| {r['run']} | {r['clients']} | {r['total_s']:.0f} | {r['training_s']:.0f} | {r['attack_macro_recall']:.3f} | "
        f"{r['benign_fpr']:.4f} | {r['boosting_accuracy']:.4f} / {r['boosting_macro_f1']:.4f} | "
        f"{r['clients_excluded_by_filter_total']} |"
    )
(out / "summary.md").write_text("\n".join(md) + "\n")
print("\n".join(md))
