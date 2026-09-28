"""Class-imbalance-capped sampling, for running the pipeline on a smaller dataset.

Edge-IIoTset's cleaned data is dominated by the benign class (~71%) with
some attack types (MITM, Fingerprinting) only a few hundred rows deep in
the full ~1.9M-row dataset. Cutting the dataset down to a manageable size
by uniform random sampling would preserve -- not reduce -- that imbalance.

This module instead does **capped stratified sampling** ("water-filling"):
every row of a scarce class is kept, and common classes are capped down
toward an equal per-class share of the target total. It does not
oversample or synthesize rows for scarce classes (e.g. no SMOTE) -- this
project's own data-quality history (the placeholder-label leak, the
column-shifted MITM rows; see PAPER_NOTES.md sect. 5.3) is a record of
synthetic-looking artifacts silently teaching a model the wrong thing, and
fabricating flow-feature rows for a security dataset risks exactly that.
The scarcest classes stay exactly as rare as they really are; only the
majority classes are cut down.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def capped_stratified_sample_indices(y: np.ndarray, target_total: int, seed: int) -> np.ndarray:
    """Select indices minimizing class imbalance, without exceeding any class's real count.

    Processes classes from scarcest to most common. At each step the
    remaining budget is split evenly across the classes not yet decided;
    a class at or under that even share keeps all of its rows (and its
    share is returned to the pool for the remaining classes); a class over
    it is capped at that share. Since classes are visited in ascending
    order, once a class exceeds its share every subsequent (larger) class
    does too, so the remainder simply splits the leftover budget evenly
    across them.

    Args:
        y: Integer class labels for every candidate row.
        target_total: Desired total sample size (the actual total may
            land slightly under this after rounding, or under it if every
            class combined has fewer than `target_total` rows).
        seed: Random seed, for reproducible per-class row selection.

    Returns:
        Row indices to keep (into `y`, and any array row-aligned with it),
        unsorted (already shuffled) -- shuffle again after concatenating
        with other data if a particular order matters.
    """
    rng = np.random.default_rng(seed)
    classes, counts = np.unique(y, return_counts=True)
    count_of = dict(zip(classes.tolist(), counts.tolist()))
    ascending = sorted(classes.tolist(), key=lambda c: count_of[c])

    remaining_budget = min(target_total, int(counts.sum()))
    remaining_classes = len(ascending)
    per_class_take: dict[int, int] = {}
    for c in ascending:
        share = remaining_budget / remaining_classes
        take = min(count_of[c], round(share))
        per_class_take[c] = take
        remaining_budget -= take
        remaining_classes -= 1

    selected_parts = []
    for c in classes.tolist():
        idx_c = np.where(y == c)[0]
        rng.shuffle(idx_c)
        selected_parts.append(idx_c[: per_class_take[c]])
    selected = np.concatenate(selected_parts)
    rng.shuffle(selected)

    logger.info(
        "Capped stratified sample: %d rows from %d classes (target %d), "
        "smallest class %d/%d rows kept, largest class %d/%d rows kept",
        len(selected),
        len(classes),
        target_total,
        per_class_take[ascending[0]],
        count_of[ascending[0]],
        per_class_take[ascending[-1]],
        count_of[ascending[-1]],
    )
    return selected


def per_class_counts(y: np.ndarray, class_names: list[str]) -> dict[str, int]:
    """`{class name: row count}` for `y`, including classes with zero rows."""
    classes, counts = np.unique(y, return_counts=True)
    found = dict(zip(classes.tolist(), counts.tolist()))
    return {name: found.get(idx, 0) for idx, name in enumerate(class_names)}
