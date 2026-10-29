#!/bin/bash
set -x
source ~/FL-IDS/venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python -m fl_ids.eval.ablation --num-rounds 20 --output-dir results/extended > logs/extended/ablation.log 2>&1
python -m fl_ids.eval.poisoning_sweep --num-rounds 20 --output-dir results/extended > logs/extended/poisoning_sweep.log 2>&1
echo QUEUE2_DONE
