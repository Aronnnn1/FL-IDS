"""Tests for the weight-pruning helpers (project Objective 3)."""

from __future__ import annotations

import numpy as np

from fl_ids.eval.pruning import prune_global_magnitude, sizes
from fl_ids.eval.simulation import prune_weight_matrices
from fl_ids.models.autoencoder import Autoencoder, get_weights


def test_prune_weight_matrices_zeroes_the_smallest_entries_and_keeps_biases():
    rng = np.random.default_rng(0)
    weights = [rng.standard_normal((10, 10)).astype(np.float32), rng.standard_normal(10).astype(np.float32)]
    pruned = prune_weight_matrices(weights, 0.5)
    assert abs((pruned[0] == 0).mean() - 0.5) < 0.02
    assert np.array_equal(pruned[1], weights[1])
    kept = np.abs(weights[0])[pruned[0] != 0]
    dropped = np.abs(weights[0])[pruned[0] == 0]
    assert kept.min() >= dropped.max()
    assert prune_weight_matrices(weights, 0.0) is weights


def test_prune_global_magnitude_matches_the_weight_list_version_and_sizes_count_non_zeros():
    model = Autoencoder(20, [16, 8], 4)
    pruned = prune_global_magnitude(model, 0.7)
    reference = prune_weight_matrices(get_weights(model), 0.7)
    for got, want in zip(get_weights(pruned), reference):
        assert np.allclose(got, want)
    s = sizes(pruned)
    assert s["nonzero_weights"] < sizes(model)["nonzero_weights"]
    assert s["dense_bytes"] == 4 * s["parameters"]
    # the original model is untouched
    assert sizes(model)["nonzero_weights"] == sum(w.size for w in get_weights(model) if w.ndim > 1)
