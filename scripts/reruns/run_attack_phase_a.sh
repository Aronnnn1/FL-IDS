#!/bin/bash
# Real multi-process Phase A with sign-flip attackers (20% and 30% of the 10 clients), for the trust-score figures.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
for F in 0.2 0.3; do
  N=mal$(echo $F | tr -d .)
  python3 - $F $N <<PY
import sys, yaml
f, n = sys.argv[1:]
cfg = yaml.safe_load(open("configs/config.yaml"))
cfg["orchestration"].update(artifact_dir=f"saved_models/attack_runs/{n}", run_dir=f"runs/attack_runs/{n}", malicious_fraction=float(f))
cfg["evaluation"]["output_dir"] = f"results/attack_runs/{n}"; cfg["logging"]["log_dir"] = f"logs/attack_runs/{n}"
open(f"configs/attack_{n}.yaml", "w").write(yaml.safe_dump(cfg, sort_keys=False))
PY
  python -m fl_ids.orchestration.phase_a --config-path configs/attack_$N.yaml > logs/attack_runs/$N.log 2>&1 && R=OK || R=FAILED
  echo "$N $R $(grep -o "Phase A done.*" logs/attack_runs/$N.log | cut -c1-200)" >> logs/attack_runs/status.log
done
echo ALL_DONE >> logs/attack_runs/status.log
