#!/bin/bash
# Full-pool real Phase A (1 server + N client processes), per-class breakdown, then Phase B on Backdoor_attack.pcap.
# bash run_full_phase_a.sh <clients> <seed>
C=$1; S=$2; T=c${C}_s${S}
cd ~/FL-IDS-clean; source venv/bin/activate
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p logs/full/$T
CFG=configs/full/$T.yaml
START=$(date +%s)
if python -m fl_ids.orchestration.phase_a --config-path $CFG > logs/full/$T/phase_a.log 2>&1; then A=OK; else A=FAILED; fi
echo "$T phase_a $A $(( $(date +%s)-START ))s $(grep -o "Phase A done.*" logs/full/$T/phase_a.log | cut -c1-200)" >> logs/full/status.log
[ $A = OK ] || exit 1
python -m fl_ids.eval.bundle_report --config-path $CFG --artifact-dir saved_models/full/$T --run-dir runs/full/$T/phase_a --output-dir results/full/$T/breakdown > logs/full/$T/bundle_report.log 2>&1 && echo "$T breakdown OK" >> logs/full/status.log
if python -m fl_ids.orchestration.phase_b --config-path $CFG --pcap data/raw/pcaps/Backdoor_attack.pcap --artifact-dir saved_models/full/$T --run-dir runs/full/$T/phase_b > logs/full/$T/phase_b.log 2>&1; then B=OK; else B=FAILED; fi
echo "$T phase_b $B $(grep -o "Phase B done.*" logs/full/$T/phase_b.log | cut -c1-230)" >> logs/full/status.log
