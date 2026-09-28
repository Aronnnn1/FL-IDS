"""Tests for capped stratified sampling (fl_ids.data.sampling).

Covers: scarce classes keep every row (no synthetic oversampling), common
classes get capped down toward an even share, the result never exceeds
the target total or fabricates rows for any class, and the selection is
reproducible given a fixed seed.
"""

from __future__ import annotations

import numpy as np

from fl_ids.data.sampling import capped_stratified_sample_indices, per_class_counts


def _skewed_labels() -> np.ndarray:
    # Class 0: 10,000 rows (dominant, like "Normal"); class 1: 500; class 2: 50 (scarce, like MITM).
    return np.concatenate([np.zeros(10_000, dtype=int), np.ones(500, dtype=int), np.full(50, 2, dtype=int)])


def test_scarce_classes_keep_every_row():
    y = _skewed_labels()
    idx = capped_stratified_sample_indices(y, target_total=1000, seed=0)
    sampled = y[idx]
    assert (sampled == 2).sum() == 50, "the scarcest class should never be cut down"


def test_result_does_not_exceed_target_or_any_class_count():
    y = _skewed_labels()
    idx = capped_stratified_sample_indices(y, target_total=1000, seed=0)
    assert len(idx) <= 1000
    counts = per_class_counts(y[idx], class_names=["a", "b", "c"])
    full_counts = per_class_counts(y, class_names=["a", "b", "c"])
    for name in counts:
        assert counts[name] <= full_counts[name]


def test_imbalance_ratio_shrinks_relative_to_the_source():
    y = _skewed_labels()
    idx = capped_stratified_sample_indices(y, target_total=1000, seed=0)
    sampled = y[idx]
    _, source_counts = np.unique(y, return_counts=True)
    _, sample_counts = np.unique(sampled, return_counts=True)
    source_ratio = source_counts.max() / source_counts.min()
    sample_ratio = sample_counts.max() / sample_counts.min()
    assert sample_ratio < source_ratio, "capping should reduce, not preserve, the majority/minority ratio"


def test_target_larger_than_dataset_returns_everything():
    y = _skewed_labels()
    idx = capped_stratified_sample_indices(y, target_total=1_000_000, seed=0)
    assert len(idx) == len(y)
    assert sorted(idx.tolist()) == list(range(len(y)))


def test_reproducible_given_same_seed():
    y = _skewed_labels()
    idx_a = capped_stratified_sample_indices(y, target_total=1000, seed=7)
    idx_b = capped_stratified_sample_indices(y, target_total=1000, seed=7)
    assert np.array_equal(np.sort(idx_a), np.sort(idx_b))


def test_no_index_out_of_bounds_or_duplicated():
    y = _skewed_labels()
    idx = capped_stratified_sample_indices(y, target_total=1000, seed=3)
    assert idx.min() >= 0
    assert idx.max() < len(y)
    assert len(np.unique(idx)) == len(idx)
