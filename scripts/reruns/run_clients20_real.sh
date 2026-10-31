#!/bin/bash
# Real multi-process 20-client Phase A (1 Flower server + 20 client processes), then Phase B on its bundle.
set -e
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
S=$(date +%s)
python -m fl_ids.orchestration.phase_a --config-path configs/config_20clients_real.yaml > logs/clients20_real/phase_a.log 2>&1
echo "PHASE_A_DONE $(($(date +%s)-S))s" >> logs/clients20_real/status.log
python -m fl_ids.orchestration.phase_b --config-path configs/config_20clients_real.yaml --pcap data/raw/pcaps/Backdoor_attack.pcap --artifact-dir saved_models/phase_a_20c_real --run-dir runs/clients20_real/phase_b > logs/clients20_real/phase_b.log 2>&1
echo "PHASE_B_DONE $(($(date +%s)-S))s" >> logs/clients20_real/status.log
