#!/bin/bash
# Ablation (30% attackers), poisoning sweep and zero-day repeated at seeds 43 and 44 (seed 42 is results/extended/).
# In-process runs, one at a time. Outputs: results/seeds/s<seed>/, logs: logs/seeds/.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p logs/seeds
for S in 43 44; do
  for M in ablation poisoning_sweep zero_day; do
    O=results/seeds/s$S; mkdir -p $O
    T=$(date +%s)
    if python -m fl_ids.eval.$M --num-rounds 20 --seed $S --output-dir $O > logs/seeds/${M}_s$S.log 2>&1; then R=OK; else R=FAILED; fi
    echo "$M s$S $R $(( $(date +%s)-T ))s" >> logs/seeds/status.log
  done
done
echo ALL_DONE >> logs/seeds/status.log
