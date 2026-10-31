#!/bin/bash
# Phase A repeats at other seeds (10 and 20 real client processes). One at a time (memory).
# Seed changes the data split, the Dirichlet partition and the model init; outputs go under */multiseed/.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
mkdir -p logs/multiseed
for C in 10 20; do for S in 43 44; do
  N=c${C}_s${S}
  python3 - $C $S $N <<PY
import sys, yaml
c, s, n = sys.argv[1:]
cfg = yaml.safe_load(open("configs/config.yaml"))
cfg["seed"] = int(s); cfg["data"]["num_clients"] = int(c)
cfg["orchestration"].update(artifact_dir=f"saved_models/multiseed/{n}", run_dir=f"runs/multiseed/{n}")
cfg["evaluation"]["output_dir"] = f"results/multiseed/{n}"; cfg["logging"]["log_dir"] = f"logs/multiseed/{n}"
open(f"configs/multiseed_{n}.yaml", "w").write(yaml.safe_dump(cfg, sort_keys=False))
PY
  T=$(date +%s)
  if python -m fl_ids.orchestration.phase_a --config-path configs/multiseed_$N.yaml > logs/multiseed/$N.log 2>&1; then
    echo "$N OK $(($(date +%s)-T))s $(grep -o cascade attack macro-recall.* logs/multiseed/$N.log | head -1)" >> logs/multiseed/status.log
  else echo "$N FAILED" >> logs/multiseed/status.log; fi
done; done
echo ALL_DONE >> logs/multiseed/status.log
