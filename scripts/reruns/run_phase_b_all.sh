#!/bin/bash
# Phase B (Mininet replay, classify, block, read the rule back) for every downloaded attack capture, on one full-pool bundle.
# bash run_phase_b_all.sh <bundle tag, e.g. c10_s42>
T=${1:-c10_s42}
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p logs/full/phase_b_all
: > logs/full/phase_b_all/summary.log
for f in data/raw/pcaps/*.pcap; do
  n=$(basename "$f" .pcap | tr " ()+" "____" | tr -s "_")
  S=$(date +%s)
  if python -m fl_ids.orchestration.phase_b --config-path configs/full/$T.yaml --pcap "$f" --artifact-dir saved_models/full/$T --run-dir runs/full/phase_b_all/$n > logs/full/phase_b_all/$n.log 2>&1; then R=OK; else R=FAILED; fi
  echo "$n | $R | $(( $(date +%s)-S ))s | $(grep -o "Phase B done.*" logs/full/phase_b_all/$n.log | cut -c1-260)" >> logs/full/phase_b_all/summary.log
done
echo ALL_DONE >> logs/full/phase_b_all/summary.log
