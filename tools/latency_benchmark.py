"""Time the cascade on real held-out packets: one packet at a time, and in batches.

Measures model inference only (classifier, autoencoder, both together) on a saved Phase A bundle. It excludes capture
reading, tshark feature extraction and the switch, so it is the cost of "deciding" once a packet's features exist.

  OMP_NUM_THREADS=1 venv/bin/python tools/latency_benchmark.py --config configs/full/c10_s42.yaml \
      --bundle saved_models/full/c10_s42 --run-dir runs/full/c10_s42 --output results/latency/c10_s42.json
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

from fl_ids.eval.bundle_report import load_run_clients
from fl_ids.eval.common import concat_client_test_slices, per_row_thresholds
from fl_ids.eval.metrics import flag_attacks
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.utils.config import load_config

MODES = ("boosting_only", "autoencoder_only", "cascade")


def cpu_name() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--single", type=int, default=3000, help="packets timed one call each")
    ap.add_argument("--batch", type=int, default=200000, help="packets in the batch run")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    config = load_config(args.config)
    art = load_phase_a_artifacts(args.bundle, config.boosting)
    X_raw, X_norm, y, client_ids = concat_client_test_slices(load_run_clients(Path(args.run_dir)))
    thr = per_row_thresholds(art.client_thresholds, client_ids)
    rng = np.random.default_rng(args.seed)

    def flags(mode, sel):
        return flag_attacks(mode, art.boosting_model, art.autoencoder, thr[sel], X_raw[sel], X_norm[sel], art.class_names, art.cascade_config)

    # warm up so one-off start-up cost is not counted
    warm = rng.choice(len(y), 200, replace=False)
    for mode in MODES:
        flags(mode, warm)

    out = {"rows_available": int(len(y)), "cpu": cpu_name(), "threads": "1 (OMP_NUM_THREADS=1)", "bundle": args.bundle, "modes": {}}
    single_idx = rng.choice(len(y), args.single, replace=False)
    batch_idx = rng.choice(len(y), min(args.batch, len(y)), replace=False)
    for mode in MODES:
        lat = np.empty(len(single_idx))
        for k, i in enumerate(single_idx):
            sel = np.array([i])
            t0 = time.perf_counter()
            flags(mode, sel)
            lat[k] = time.perf_counter() - t0
        t0 = time.perf_counter()
        flags(mode, batch_idx)
        batch_s = time.perf_counter() - t0
        out["modes"][mode] = {
            "single_packet_ms": {
                "median": float(np.median(lat) * 1e3),
                "p95": float(np.percentile(lat, 95) * 1e3),
                "p99": float(np.percentile(lat, 99) * 1e3),
                "n": int(len(lat)),
            },
            "batch": {"packets": int(len(batch_idx)), "seconds": batch_s, "us_per_packet": batch_s / len(batch_idx) * 1e6,
                      "packets_per_second": len(batch_idx) / batch_s},
        }
        print(mode, json.dumps(out["modes"][mode]), flush=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2))
    print("wrote", args.output)


if __name__ == "__main__":
    main()
