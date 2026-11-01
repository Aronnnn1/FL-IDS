"""Run the ablation, poisoning sweep and zero-day experiments for seeds 43 and 44 as independent parallel shards.

Each federated training is single-threaded and independent of the others, so they are run side by side instead of in a
queue: the ablation is one job, the sweep is one job per poisoning fraction, the zero-day experiment one job per held-out
class. Every job rebuilds the same evaluation setup from the same seed, so a shard gives the numbers the serial run would.
Per-job configs and logs live under results/seeds/s<seed>/shards/ and logs/seeds/; merged CSVs land next to them.

    python3 tools/run_sharded_seeds.py --workers 12
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (43, 44)
FRACTIONS = (0.0, 0.2, 0.3, 0.4, 0.5)
CLASSES = ["Backdoor", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP", "Fingerprinting", "MITM", "Password",
           "Port_Scanning", "Ransomware", "SQL_injection", "Uploading", "Vulnerability_scanner", "XSS"]
ENV = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}


def make_jobs():
    base = yaml.safe_load(open(ROOT / "configs/config.yaml"))
    jobs = []
    for seed in SEEDS:
        shards = ROOT / f"results/seeds/s{seed}/shards"
        shards.mkdir(parents=True, exist_ok=True)

        def add(module, name, evaluation, extra=()):
            cfg = yaml.safe_load(yaml.safe_dump(base))
            cfg["evaluation"].update(evaluation)
            cfg_path = shards / f"{name}.yaml"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
            out = shards / name
            jobs.append((name, [sys.executable, "-m", f"fl_ids.eval.{module}", "--config-path", str(cfg_path), "--num-rounds", "20",
                                "--seed", str(seed), "--output-dir", str(out), *extra], ROOT / f"logs/seeds/{name}.log", out))

        add("ablation", f"ablation_s{seed}", {}, ("--skip-zero-day",))
        for f in FRACTIONS:
            add("poisoning_sweep", f"sweep_s{seed}_f{int(f * 100):02d}", {"poisoning_fractions": [f]}, ("--skip-zero-day",))
        for c in CLASSES:
            add("zero_day", f"zeroday_s{seed}_{c}", {"zero_day_holdout_classes": [c]})
    return jobs


def run(job):
    name, cmd, log, out = job
    if (out / ".done").exists():
        return name, "skipped (done)"
    out.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as fh:
        rc = subprocess.call(cmd, cwd=ROOT, env=ENV, stdout=fh, stderr=subprocess.STDOUT)
    if rc == 0:
        (out / ".done").write_text("ok")
    return name, "OK" if rc == 0 else f"FAILED rc={rc}"


def merge():
    for seed in SEEDS:
        shards = ROOT / f"results/seeds/s{seed}/shards"
        dest = ROOT / f"results/seeds/s{seed}"
        for pattern, fname in ((f"sweep_s{seed}_f*", "poisoning_resistance_sweep.csv"), (f"zeroday_s{seed}_*", "zero_day_holdout.csv")):
            rows, header = [], None
            for d in sorted(shards.glob(pattern)):
                p = d / fname
                if p.is_file():
                    with open(p) as fh:
                        reader = csv.DictReader(fh)
                        header = reader.fieldnames
                        rows.extend(reader)
            if rows:
                with open(dest / fname, "w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=header)
                    w.writeheader()
                    w.writerows(rows)
                print("merged", dest / fname, len(rows), "rows")
        for fname in ("ablation_table.csv", "ablation_per_class_recall.csv"):
            p = shards / f"ablation_s{seed}" / fname
            if p.is_file():
                (dest / fname).write_text(p.read_text())
                print("copied", dest / fname)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--merge-only", action="store_true")
    args = parser.parse_args()
    if not args.merge_only:
        jobs = make_jobs()
        print(len(jobs), "jobs,", args.workers, "workers", flush=True)
        with ThreadPoolExecutor(args.workers) as pool:
            for name, status in pool.map(run, jobs):
                print(status, name, flush=True)
    merge()
    print("SHARDS_DONE", flush=True)
