#!/bin/bash
# Phase B (Backdoor_attack.pcap through Mininet) on each multi-seed Phase A bundle.
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
for N in c10_s43 c10_s44 c20_s43 c20_s44; do
  if python -m fl_ids.orchestration.phase_b --config-path configs/multiseed_$N.yaml --pcap data/raw/pcaps/Backdoor_attack.pcap \
      --artifact-dir saved_models/multiseed/$N --run-dir runs/multiseed/$N/phase_b > logs/multiseed/${N}_phase_b.log 2>&1; then R=OK; else R=FAILED; fi
  echo "$N phase_b $R $(grep -o "Phase B done.*" logs/multiseed/${N}_phase_b.log | cut -c1-230)" >> logs/multiseed/status_phase_b.log
done
echo ALL_DONE >> logs/multiseed/status_phase_b.log
