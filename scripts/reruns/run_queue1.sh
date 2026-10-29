#!/bin/bash
set -x
source ~/FL-IDS/venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python -m fl_ids.eval.stage_report --num-rounds 20 --output-dir results/extended > logs/extended/stage_report.log 2>&1
python -m fl_ids.eval.zero_day --num-rounds 20 --output-dir results/extended > logs/extended/zero_day.log 2>&1
python -m fl_ids.eval.multiseed_check --num-rounds 20 --output-dir results/extended > logs/extended/multiseed.log 2>&1
echo QUEUE1_DONE
