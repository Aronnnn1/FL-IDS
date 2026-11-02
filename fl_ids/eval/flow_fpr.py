"""False alarms on benign traffic, counted per connection as well as per packet, for a connection-grouped full-pool bundle.

Packet-level FPR hides how concentrated false alarms are: a client's benign test set can be dominated by a few very long
connections, and one flagged connection then flags thousands of packets. This rebuilds the clients' train/val/test split
(deterministic given the config and seed, so it reproduces the Phase A run's test slices), reloads the bundle, and reports,
per client and overall:
  * packet-level FPR (the number Phase A logs),
  * connection-level FPR (share of benign test connections where at least half of the packets are flagged),
  * how many connections / packets the worst offenders account for.

    python -m fl_ids.eval.flow_fpr --config-path configs/full/c10_s42.yaml --artifact-dir saved_models/full/c10_s42 \
        --run-dir runs/full/c10_s42/phase_a --output-dir results/full/c10_s42/flow_fpr
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from fl_ids.data.pipeline import (
    _split_client_data_grouped,
    grouped_dirichlet_partition,
    load_and_encode,
    load_flow_ids,
    server_pool_split,
)
from fl_ids.eval.bundle_report import load_run_clients
from fl_ids.eval.common import concat_client_test_slices, per_row_thresholds
from fl_ids.eval.metrics import flag_attacks
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.utils.config import load_config

logger = logging.getLogger(__name__)


def rebuild_test_groups(config) -> dict[int, np.ndarray]:
    """Flow id of every row of every client's test slice, in the order Phase A saved them."""
    X, y, _enc, _names, benign = load_and_encode(
        config.data.dnn_csv_path, config.data.capture_repairs, config.data.extended_features, config.data.feature_cache
    )
    _xc, _yc, X_pool, y_pool, _gc, g_pool = server_pool_split(X, y, config, config.seed, config.orchestration.pool_subsample_size)
    parts = grouped_dirichlet_partition(y_pool, g_pool, config.data.num_clients, config.data.dirichlet_alpha, config.seed)
    out = {}
    for cid, idx in parts.items():
        _tr, _va, te = _split_client_data_grouped(
            idx, y_pool, g_pool, benign, config.data.val_benign_fraction, config.data.test_fraction, seed=config.seed + cid
        )
        out[cid] = g_pool[te]
    return out


def flow_fpr(config_path: str, artifact_dir: str, run_dir: str, output_dir: str) -> dict:
    config = load_config(config_path)
    art = load_phase_a_artifacts(artifact_dir, config.boosting)
    clients = load_run_clients(Path(run_dir))
    test_groups = rebuild_test_groups(config)
    for cid, d in clients.items():  # the rebuild must reproduce the saved slices exactly
        if len(test_groups[cid]) != len(d["y_test"]):
            raise RuntimeError(f"client {cid}: rebuilt test slice has {len(test_groups[cid])} rows, saved one {len(d['y_test'])}")
    X_raw, X_norm, y, client_ids = concat_client_test_slices(clients)
    groups = np.concatenate([test_groups[cid] for cid in sorted(clients)])
    flags = flag_attacks("cascade", art.boosting_model, art.autoencoder, per_row_thresholds(art.client_thresholds, client_ids),
                         X_raw, X_norm, art.class_names, art.cascade_config)
    benign = y == art.benign_class
    df = pd.DataFrame({"client": client_ids[benign], "flow": groups[benign], "flag": flags[benign]})
    per_flow = df.groupby(["client", "flow"]).agg(rows=("flag", "size"), flagged=("flag", "mean")).reset_index()
    per_flow["false_alarm"] = per_flow["flagged"] >= 0.5
    rows = []
    for cid, g in per_flow.groupby("client"):
        sel = df[df.client == cid]
        rows.append({"client": int(cid), "benign_test_rows": int(len(sel)), "benign_test_flows": int(len(g)),
                     "packet_fpr": float(sel.flag.mean()), "flow_fpr": float(g.false_alarm.mean()),
                     "largest_flow_rows": int(g.rows.max()), "largest_flow_share": float(g.rows.max() / len(sel)),
                     "flagged_packets_in_false_alarm_flows": int(g.loc[g.false_alarm, "rows"].sum())})
    per_client = pd.DataFrame(rows)
    top = per_flow.sort_values("rows", ascending=False).head(15)
    total = {
        "packet_fpr": float(df.flag.mean()), "flow_fpr": float(per_flow.false_alarm.mean()),
        "benign_test_rows": int(len(df)), "benign_test_flows": int(len(per_flow)),
        "median_client_packet_fpr": float(per_client.packet_fpr.median()),
        "share_of_false_alarm_packets_from_top_10_flows": float(
            per_flow.assign(fp=per_flow.rows * per_flow.flagged).sort_values("fp", ascending=False).head(10).fp.sum() / max(df.flag.sum(), 1)),
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    per_client.to_csv(out / "per_client_flow_fpr.csv", index=False)
    top.to_csv(out / "largest_benign_flows.csv", index=False)
    (out / "summary.json").write_text(json.dumps(total, indent=2))
    return {"total": total, "per_client": per_client, "top": top}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    res = flow_fpr(args.config_path, args.artifact_dir, args.run_dir, args.output_dir)
    print(json.dumps(res["total"], indent=2))
    print(res["per_client"].to_string(index=False))
    print(res["top"].to_string(index=False))


if __name__ == "__main__":
    main()
