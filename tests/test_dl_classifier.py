"""Tests for the supervised DL classifier (fl_ids.models.dl_classifier).

Mirrors tests/test_boosting.py's structure for the same task (cold-start
training, valid probability outputs) so the two classifiers are held to
comparable checks, since fl_ids.eval.classifier_comparison compares them
head-to-head.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from fl_ids.data.synthetic import make_synthetic_attack_dataset
from fl_ids.models.dl_classifier import DLClassifier, count_parameters, predict_proba, train_dl_classifier
from fl_ids.utils.config import DLClassifierConfig

BENIGN_CLASS = 0  # "Normal" is index 0 in make_synthetic_attack_dataset's default classes


def _dl_config(**overrides) -> DLClassifierConfig:
    defaults = dict(hidden_dims=[32, 16], learning_rate=1e-2, epochs=10, batch_size=64, dropout=0.0)
    defaults.update(overrides)
    return DLClassifierConfig(**defaults)


def test_dl_classifier_trains_and_predicts_valid_probabilities():
    X, y, class_names = make_synthetic_attack_dataset(n_samples=2000, seed=1)
    X_train, X_test, y_train, _ = train_test_split(X, y, test_size=0.3, random_state=1, stratify=y)
    scaler = StandardScaler().fit(X_train)
    X_train_std = scaler.transform(X_train).astype(np.float32)
    X_test_std = scaler.transform(X_test).astype(np.float32)

    model = DLClassifier(input_dim=X.shape[1], hidden_dims=[32, 16], num_classes=len(class_names))
    train_dl_classifier(model, X_train_std, y_train, _dl_config(), seed=1)

    proba = predict_proba(model, X_test_std)
    assert proba.shape == (len(X_test_std), len(class_names))
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-4)
    assert np.all(proba >= 0.0) and np.all(proba <= 1.0)


def test_cold_start_bootstrap_metrics_on_held_out_slice():
    """Same bar test_boosting.py's cold-start test applies to boosting: trains
    on a small calibration-sized slice, evaluates on a much larger held-out
    slice, and asserts the model is reasonably decent -- not just that it runs."""
    config = _dl_config(epochs=30)
    X, y, class_names = make_synthetic_attack_dataset(n_samples=30_000, seed=2)

    X_calib, X_held_out, y_calib, y_held_out = train_test_split(
        X, y, train_size=0.05, random_state=2, stratify=y
    )
    scaler = StandardScaler().fit(X_calib)
    X_calib_std = scaler.transform(X_calib).astype(np.float32)
    X_held_out_std = scaler.transform(X_held_out).astype(np.float32)

    model = DLClassifier(input_dim=X.shape[1], hidden_dims=[32, 16], num_classes=len(class_names))
    train_dl_classifier(model, X_calib_std, y_calib, config, seed=2)

    y_pred = np.argmax(predict_proba(model, X_held_out_std), axis=1)
    weighted_f1 = f1_score(y_held_out, y_pred, average="weighted", zero_division=0)

    assert len(X_calib) < len(X_held_out) * 0.1, "calibration slice should be small relative to held-out data"
    assert weighted_f1 > 0.5, f"cold-start bootstrap model should show real signal, got weighted F1={weighted_f1:.3f}"


def test_count_parameters_matches_manual_calculation():
    model = DLClassifier(input_dim=10, hidden_dims=[8, 4], num_classes=3)
    # Linear(10,8): 10*8+8=88; Linear(8,4): 8*4+4=36; Linear(4,3): 4*3+3=15. Total 139.
    assert count_parameters(model) == 88 + 36 + 15
