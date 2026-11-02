"""Run the in-process experiments on the full pool (split by connection) as independent parallel jobs.

One federated training per job. Jobs claim themselves with a lock directory, so several instances of this script can run at
the same time (start more workers whenever cores free up) without repeating work, and a finished job leaves a `.done` marker.

    python3 tools/run_full_experiments.py --workers 8 [--seeds 42 43 44] [--list]

Per seed (stealth, pruning and no-clip only for --extras-for seeds): ablation variants (4; its full-pipeline row is the sweep's 30% point), poisoning sweep (5 fractions), zero-day
(14 held-out classes), stealth attacker (3 fractions; its sign-flip counterpart is the sweep), pruning during FL (4 sparsities;
0% is the sweep's 0% point), and the no-clip run. Outputs: results/full/inprocess/s<seed>/shards/<job>/, logs: logs/full/inprocess/.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FRACTIONS = (0.0, 0.2, 0.3, 0.4, 0.5)
CLASSES = ["Backdoor", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP", "Fingerprinting", "MITM", "Password",
           "Port_Scanning", "Ransomware", "SQL_injection", "Uploading", "Vulnerability_scanner", "XSS"]
VARIANTS = ("plain_fedavg", "trimmed_mean_only", "autoencoder_only", "boosting_only")
ENV = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}


def make_jobs(seeds, extras_for=(42,)):
    base = yaml.safe_load(open(ROOT / "configs/full/base.yaml"))
    jobs = []
    for seed in seeds:
        shards = ROOT / f"results/full/inprocess/s{seed}/shards"
        shards.mkdir(parents=True, exist_ok=True)

        def add(module, name, evaluation, extra=()):
            cfg = yaml.safe_load(yaml.safe_dump(base))
            cfg["seed"] = seed
            cfg["evaluation"].update(evaluation)
            cfg_path = shards / f"{name}.yaml"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
            out = shards / name
            jobs.append((name, [sys.executable, "-m", f"fl_ids.eval.{module}", "--config-path", str(cfg_path), "--num-rounds", "20",
                                "--seed", str(seed), "--output-dir", str(out), *extra], ROOT / f"logs/full/inprocess/{name}.log", out))

        for f in FRACTIONS:
            add("poisoning_sweep", f"sweep_s{seed}_f{int(f * 100):02d}", {"poisoning_fractions": [f]}, ("--skip-zero-day",))
        for c in CLASSES:
            add("zero_day", f"zeroday_s{seed}_{c}", {"zero_day_holdout_classes": [c]})
        for v in VARIANTS:
            add("ablation", f"ablation_s{seed}_{v}", {}, ("--skip-zero-day", "--variants", v))
        if seed not in extras_for:
            continue
        for f in (0.2, 0.3, 0.4):
            add("adaptive_attack", f"stealth_s{seed}_f{int(f * 100):02d}", {}, ("--attacks", "stealth", "--fractions", str(f)))
        for sp in (0.5, 0.7, 0.8, 0.9):
            add("pruning_fl", f"prunefl_s{seed}_sp{int(sp * 100):02d}", {}, ("--sparsities", str(sp)))
        add("clip_comparison", f"noclip_s{seed}", {}, ("--only", "no clip"))
    return jobs


def run(job):
    name, cmd, log, out = job
    if (out / ".done").exists():
        return name, "skipped (done)"
    try:
        out.mkdir(parents=True, exist_ok=True)
        os.mkdir(out / ".claim")  # atomic: only one instance runs a job
    except FileExistsError:
        return name, "skipped (claimed)"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as fh:
        rc = subprocess.call(cmd, cwd=ROOT, env=ENV, stdout=fh, stderr=subprocess.STDOUT)
    if rc == 0:
        (out / ".done").write_text("ok")
    else:
        os.rmdir(out / ".claim")  # let a later instance retry
    return name, "OK" if rc == 0 else f"FAILED rc={rc}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extras-for", nargs="*", type=int, default=[42], help="seeds that also run the stealth, pruning and no-clip jobs")
    args = parser.parse_args()
    jobs = make_jobs(args.seeds, tuple(args.extras_for))
    if args.list:
        print(len(jobs), "jobs")
        for j in jobs:
            print(j[0], "done" if (j[3] / ".done").exists() else "")
        sys.exit(0)
    print(len(jobs), "jobs,", args.workers, "workers", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        for name, status in pool.map(run, jobs):
            print(status, name, flush=True)
    print("RUNNER_DONE", flush=True)
