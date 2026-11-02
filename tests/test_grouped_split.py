"""Connection-grouped splits: no flow may appear on two sides of the calibration split, the partition or a client's split."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from fl_ids.data.pipeline import (
    calibration_eval_split,
    grouped_dirichlet_partition,
    partition_and_normalize_clients,
    server_pool_split,
)
from tests.test_strategy import _full_config


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(0)
    y_parts, g_parts, next_flow = [], [], 0
    for cls, n_flows in ((0, 400), (1, 120), (2, 60), (3, 1)):  # class 3 is a single flow, like MITM
        sizes = rng.integers(1, 30, size=n_flows) if cls != 3 else np.array([300])
        for s in sizes:
            y_parts.append(np.full(s, cls))
            g_parts.append(np.full(s, next_flow))
            next_flow += 1
    y, g = np.concatenate(y_parts), np.concatenate(g_parts)
    X = rng.standard_normal((len(y), 6)).astype(np.float32)
    X[:, 0] = g  # row-aligned marker: recovers a row's flow after any split
    return X, y, g


def _config():
    config = _full_config()
    return dataclasses.replace(
        config,
        data=dataclasses.replace(config.data, group_by_flow=True, num_clients=4, min_flows_per_class=5, normalize_per_client=False),
        boosting=dataclasses.replace(config.boosting, calibration_fraction=0.1, calibration_eval_fraction=0.2),
    )


def test_calibration_split_keeps_flows_whole_and_puts_a_scarce_class_wholly_in_calibration(data):
    X, y, g = data
    X_calib, y_calib, X_pool, y_pool, g_calib, g_pool = server_pool_split(X, y, _config(), 1, None, groups=g)
    assert not set(g_calib) & set(g_pool)
    assert (y_calib == 3).sum() == 300 and (y_pool == 3).sum() == 0
    for cls in (0, 1, 2):
        share = (y_calib == cls).sum() / (y == cls).sum()
        assert 0.03 < share < 0.25, (cls, share)
    assert len(X_calib) + len(X_pool) == len(X)


def test_pool_cap_and_excluded_classes_are_applied_by_flow(data):
    X, y, g = data
    _, _, X_pool, y_pool, _, g_pool = server_pool_split(X, y, _config(), 1, 1500, groups=g)
    assert 800 < len(y_pool) < 2500
    _, y_c, _, y_p, _, _ = server_pool_split(X, y, _config(), 1, None, excluded_classes=frozenset({1}), groups=g)
    assert 1 not in set(y_c) | set(y_p)


def test_calibration_eval_split_never_holds_back_a_scarce_class(data):
    X, y, g = data
    config = _config()
    X_c, y_c, _, _, g_c, _ = server_pool_split(X, y, config, 1, None, groups=g)
    X_train, X_eval, y_train, y_eval = calibration_eval_split(X_c, y_c, g_c, config, 1)
    assert 3 not in set(y_eval) and (y_train == 3).sum() == 300
    assert not set(X_train[:, 0]) & set(X_eval[:, 0])


def test_partition_and_client_splits_share_no_flow(data):
    X, y, g = data
    config = _config()
    _, _, X_pool, y_pool, _, g_pool = server_pool_split(X, y, config, 1, None, groups=g)
    clients = partition_and_normalize_clients(X_pool, y_pool, 0, config.data, seed=2, groups=g_pool)
    seen = {}
    for cid, d in clients.items():
        for part in ("X_raw", "X_val_benign", "X_test_raw"):
            for flow in set(d[part][:, 0]):
                assert seen.setdefault(flow, cid) == cid, f"flow {flow} on clients {seen[flow]} and {cid}"
    for d in clients.values():
        sets = [set(d[k][:, 0]) for k in ("X_raw", "X_val_benign", "X_test_raw")]
        assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
    assert sum(len(d["y_test"]) for d in clients.values()) > 0


def test_grouped_partition_follows_a_skewed_dirichlet_draw_and_needs_flow_ids(data):
    X, y, g = data
    parts = grouped_dirichlet_partition(y, g, 4, 0.3, seed=3)
    assert sorted(np.concatenate(list(parts.values())).tolist()) == list(range(len(y)))
    shares = np.array([[(y[p] == c).sum() for c in (0, 1, 2)] for p in parts.values()], dtype=float)
    assert (shares / shares.sum(axis=0)).max() > 0.45  # non-IID: some client holds a large share of some class
    with pytest.raises(ValueError):
        partition_and_normalize_clients(X, y, 0, _config().data, seed=1)


def test_default_config_is_still_the_row_level_split(data):
    X, y, _ = data
    base = _config()
    config = dataclasses.replace(base, data=dataclasses.replace(base.data, group_by_flow=False))
    X_calib, y_calib, X_pool, y_pool, g_calib, g_pool = server_pool_split(X, y, config, 1, None)
    assert g_calib is None and g_pool is None
    assert abs(len(X_calib) / len(X) - 0.1) < 0.01
