#!/bin/bash
# Ablation (30% attackers) and poisoning sweep without their per-held-out-class zero-day columns, then the standalone
# zero-day experiment, for one seed: bash run_seed_sweeps_fast.sh <seed>. The zero-day columns inside the ablation and
# the sweep are ~85 extra federated trainings per seed (hours), so they are not repeated; the standalone zero-day is.
S=$1
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
O=results/seeds/s$S; mkdir -p $O logs/seeds
for M in ablation poisoning_sweep zero_day; do
  EXTRA=""; [ $M != zero_day ] && EXTRA="--skip-zero-day"
  T=$(date +%s)
  if python -m fl_ids.eval.$M --num-rounds 20 --seed $S --output-dir $O $EXTRA > logs/seeds/${M}_s$S.log 2>&1; then R=OK; else R=FAILED; fi
  echo "$M s$S $R $(( $(date +%s)-T ))s" >> logs/seeds/status_fast_s$S.log
done
echo ALL_DONE >> logs/seeds/status_fast_s$S.log
