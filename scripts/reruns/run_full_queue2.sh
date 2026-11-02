#!/bin/bash
# After the OOM of 2026-11-01 17:35 (20 client processes + 7 in-process jobs): real Phase A runs first, alone; then the in-process experiments.
cd ~/FL-IDS-clean
for TS in "20 42" "10 43" "20 43" "10 44" "20 44"; do bash scripts/reruns/run_full_phase_a.sh $TS; done
echo QUEUE_DONE >> logs/full/status.log
