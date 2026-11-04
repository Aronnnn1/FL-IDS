"""Host-level verdict for the live arena: one window of a host's packets -> attack / benign.

A window is the host's first `WINDOW_PACKETS` packets. The host is called an attacker when at least
`SHARE_THRESHOLD` of the window's packets are flagged by the cascade (the unmodified per-packet rule:
boosting at >= 0.7, else the client's autoencoder). Phase B's older rule ("any flagged packet makes the
device an attacker") would block a normal host after its first false alarm, because the autoencoder is
set to flag about 3% of normal packets by design.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from fl_ids.models.cascade import BENIGN_LABEL, cascade_predict

WINDOW_PACKETS = 3000
SHARE_THRESHOLD = 0.25


@dataclass
class WindowVerdict:
    label: str            # attack type, "anomalous", or "benign"
    is_attack: bool
    confidence: float
    stage: str            # which cascade stage made most of the calls
    share_flagged: float
    num_packets: int
    num_flagged: int
    by_label: dict

    def to_dict(self) -> dict:
        return asdict(self)


def window_verdict(artifacts, client_id: int, X_raw: np.ndarray, share_threshold: float = SHARE_THRESHOLD) -> WindowVerdict:
    out = cascade_predict(
        artifacts.boosting_model, artifacts.autoencoder, artifacts.client_thresholds[client_id],
        X_raw, artifacts.normalize(client_id, X_raw), artifacts.class_names, artifacts.cascade_config,
    )
    flagged = out.predicted_label != BENIGN_LABEL
    n, k = len(X_raw), int(flagged.sum())
    share = k / max(n, 1)
    labels, counts = np.unique(out.predicted_label, return_counts=True)
    by_label = {str(a): int(b) for a, b in zip(labels, counts)}
    if share >= share_threshold and k:
        fl_labels, fl_counts = np.unique(out.predicted_label[flagged], return_counts=True)
        label = str(fl_labels[np.argmax(fl_counts)])
        chosen = flagged & (out.predicted_label == label)
        stages, sc = np.unique(out.stage[chosen], return_counts=True)
        return WindowVerdict(label, True, float(out.confidence[chosen].mean()), str(stages[np.argmax(sc)]),
                             share, n, k, by_label)
    stages, sc = np.unique(out.stage, return_counts=True)
    return WindowVerdict(BENIGN_LABEL, False, float(1.0 - share), str(stages[np.argmax(sc)]), share, n, k, by_label)
