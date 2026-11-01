#!/bin/bash
# Adaptive attacker, pruning during FL, clipping comparison, single-feature AUROC. In-process, one at a time.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p logs/adaptive logs/pruning logs/clip logs/leak
python -m fl_ids.eval.adaptive_attack --num-rounds 20 --seed 42 --output-dir results/adaptive > logs/adaptive/adaptive_attack.log 2>&1; echo "adaptive $?" >> logs/queue3.status
python -m fl_ids.eval.pruning_fl --num-rounds 20 --output-dir results/pruning > logs/pruning/pruning_during_fl.log 2>&1; echo "pruning_fl $?" >> logs/queue3.status
python -m fl_ids.eval.clip_comparison --num-rounds 20 --output-dir results/clip > logs/clip/clip_comparison.log 2>&1; echo "clip $?" >> logs/queue3.status
python tools/leak_auroc.py > logs/leak/leak_auroc.log 2>&1; echo "leak_auroc $?" >> logs/queue3.status
echo QUEUE3_DONE >> logs/queue3.status
