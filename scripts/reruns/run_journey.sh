#!/bin/bash
# Timed end-to-end journey: real Phase A (10 client processes) then Phase B on its bundle.
# Each phase writes journey.json (stage timings) to its run directory. Run from the repo root.
set -e
source ~/FL-IDS/venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
python -m fl_ids.orchestration.phase_a --config-path configs/config_journey.yaml > logs/journey/phase_a.log 2>&1
python -m fl_ids.orchestration.phase_b --config-path configs/config_journey.yaml --pcap data/raw/pcaps/Backdoor_attack.pcap --artifact-dir saved_models/phase_a_journey --run-dir runs/journey/phase_b > logs/journey/phase_b.log 2>&1
echo JOURNEY_DONE >> logs/journey/phase_b.log
