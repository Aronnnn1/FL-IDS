#!/bin/bash
# The remaining full-pool real Phase A runs, one after another (each uses ports/state files of a single run).
cd ~/FL-IDS-clean
while tmux has-session -t full10 2>/dev/null; do sleep 10; done
for TS in "20 42" "10 43" "20 43" "10 44" "20 44"; do bash scripts/reruns/run_full_phase_a.sh $TS; done
echo QUEUE_DONE >> logs/full/status.log
