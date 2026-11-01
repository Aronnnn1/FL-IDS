#!/bin/bash
# Seed 44 half of run_seed_sweeps.sh, run in parallel with seed 43 to save wall-clock time.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
S=44; O=results/seeds/s$S; mkdir -p $O logs/seeds
for M in ablation poisoning_sweep zero_day; do
  T=$(date +%s)
  if python -m fl_ids.eval.$M --num-rounds 20 --seed $S --output-dir $O > logs/seeds/${M}_s$S.log 2>&1; then R=OK; else R=FAILED; fi
  echo "$M s$S $R $(( $(date +%s)-T ))s" >> logs/seeds/status44.log
done
echo ALL_DONE >> logs/seeds/status44.log
