"""Supervised deep-learning classifier -- a direct alternative to LightGBM
boosting for attack-type classification (compared in
`fl_ids.eval.classifier_comparison`, not part of the cascade or FL).

**This is a different comparison from the `autoencoder_only` ablation
variant** (`fl_ids.eval.variants`). That variant tests the *unsupervised*
autoencoder (component 3) alone as a binary anomaly detector, scored by
thresholding reconstruction error -- it answers "is an unsupervised
detector a viable substitute for a classifier". This module is a
*supervised* classifier, trained on the same attack-type labels boosting
uses, predicting a class the same way boosting does (softmax probabilities
over the label taxonomy) -- it answers "of two classifiers, which is more
accurate". Reconstruction error plays no role here; nothing in this module
reconstructs its input.

**Feature scale.** Unlike `fl_ids.models.boosting` (always raw features --
see its module docstring), this model is trained on standardized features:
a dense net trained on raw Edge-IIoTset flow features (values spanning many
orders of magnitude -- packet counts vs. byte counts vs. flags) converges
far worse than one trained on standardized input, whereas a tree-based
model's per-feature splits are scale-invariant. `fl_ids.eval.
classifier_comparison` fits one `StandardScaler` on the shared training
split and applies it only to this model's input, keeping boosting on raw
features -- the same "give each model type the representation it needs"
principle `fl_ids.models.boosting`'s docstring documents, applied in
reverse.
"""

from __future__ import annotations

import logging

import numpy as np
import torch
from torch import nn

from fl_ids.utils.config import DLClassifierConfig

logger = logging.getLogger(__name__)


def _build_mlp(dims: list[int], dropout: float) -> nn.Sequential:
    """Dense MLP: ReLU (+ dropout, if configured) between layers, linear logits out."""
    layers: list[nn.Module] = []
    for i in range(len(dims) - 1):
        layers.append(nn.Linear(dims[i], dims[i + 1]))
        if i < len(dims) - 2:
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
    return nn.Sequential(*layers)


class DLClassifier(nn.Module):
    """Dense feedforward classifier over standardized tabular flow features."""

    def __init__(self, input_dim: int, hidden_dims: list[int], num_classes: int, dropout: float = 0.0) -> None:
        """Initialize the network.

        Args:
            input_dim: Number of input features.
            hidden_dims: Hidden layer widths, in order from input to output.
            num_classes: Number of attack-type classes (including benign).
            dropout: Dropout probability between hidden layers (0 disables).
        """
        super().__init__()
        self.input_dim = input_dim
        self.num_classes = num_classes
        self.net = _build_mlp([input_dim, *hidden_dims, num_classes], dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return raw (pre-softmax) class logits."""
        return self.net(x)


def train_dl_classifier(
    model: DLClassifier,
    X: np.ndarray,
    y: np.ndarray,
    config: DLClassifierConfig,
    seed: int,
) -> list[float]:
    """Train with cross-entropy loss on labeled attack-type data.

    Args:
        model: The classifier to train, in place.
        X: Standardized feature matrix, shape (n_samples, input_dim).
        y: Integer-encoded attack-type labels, shape (n_samples,).
        config: Training hyperparameters (learning_rate, epochs, batch_size).
        seed: Random seed, for reproducible batch shuffling and init.

    Returns:
        Mean cross-entropy loss per epoch, in training order.
    """
    torch.manual_seed(seed)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    criterion = nn.CrossEntropyLoss()
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.long)
    n = len(X_tensor)

    logger.info(
        "Training DL classifier: %d samples, %d classes, %d epochs",
        n, model.num_classes, config.epochs,
    )
    epoch_losses: list[float] = []
    for epoch in range(config.epochs):
        perm = torch.randperm(n)
        batch_losses = []
        for start in range(0, n, config.batch_size):
            idx = perm[start : start + config.batch_size]
            optimizer.zero_grad()
            logits = model(X_tensor[idx])
            loss = criterion(logits, y_tensor[idx])
            loss.backward()
            optimizer.step()
            batch_losses.append(loss.item())
        mean_loss = float(np.mean(batch_losses)) if batch_losses else 0.0
        epoch_losses.append(mean_loss)
        logger.debug("DL classifier epoch %d/%d: mean loss %.4f", epoch + 1, config.epochs, mean_loss)
    return epoch_losses


def predict_proba(model: DLClassifier, X: np.ndarray) -> np.ndarray:
    """Per-class predicted probabilities (softmax over logits), shape (n_samples, num_classes).

    Mirrors `fl_ids.models.boosting.BoostingClassifier.predict_proba`'s
    interface so both classifiers can be scored with the same evaluation
    code (`fl_ids.eval.metrics`).

    Args:
        model: A trained (or in-training) classifier.
        X: Standardized feature matrix, shape (n_samples, input_dim).

    Returns:
        Row-stochastic probability matrix, shape (n_samples, num_classes).
    """
    model.eval()
    with torch.no_grad():
        X_tensor = torch.tensor(X, dtype=torch.float32)
        proba = torch.softmax(model(X_tensor), dim=1)
    return proba.numpy()


def count_parameters(model: DLClassifier) -> int:
    """Total trainable parameter count -- for reporting model size alongside LightGBM's."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
