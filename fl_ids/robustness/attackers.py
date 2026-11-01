"""Test attacker for the trust filter (component 5's validation case).

CLAUDE.md is explicit about which attack actually validates this defense:
corrupting a malicious client's *local input data* mostly just looks like
non-IID heterogeneity to an unsupervised autoencoder — it never sees
labels, so label-flipping does nothing, and scaled/shifted input just
produces "yet another differently-distributed client." To actually test
the trust filter, the attacker needs to corrupt the *update itself*. A
sign-flip / gradient-ascent attack (negate and amplify the true delta
before sending it) is the standard Byzantine test case this component is
built for.

It can also lie about its dataset size (`claimed_num_examples`). Plain
FedAvg weights each update by the example count the client reports, so an
attacker reporting its true, possibly small, count barely moves the
average; attackers in the poisoning literature inflate it. The trust
filter and trimmed mean ignore reported counts, so this only strengthens
the attack against the FedAvg baseline -- which is the comparison it's for.
"""

from __future__ import annotations

import numpy as np
from flwr.common import NDArrays, Scalar

from fl_ids.fl.client import AutoencoderClient
from fl_ids.utils.config import RobustnessConfig

ATTACKER_COUNT_MODES = ("honest", "max_client")
ATTACK_KINDS = ("sign_flip", "stealth")


def attacker_claimed_examples(config: RobustnessConfig, client_train_sizes: list[int]) -> int | None:
    """The example count attackers report, per `robustness.attacker_example_count`.

    Args:
        config: Robustness config.
        client_train_sizes: Every client's training-row count (the harness
            running the federation knows these; a real attacker would just
            claim a large number).

    Returns:
        None for "honest" (report the true count), else the largest
        client's training-row count.

    Raises:
        ValueError: On an unknown mode.
    """
    mode = config.attacker_example_count
    if mode == "honest":
        return None
    if mode == "max_client":
        return int(max(client_train_sizes))
    raise ValueError(f"robustness.attacker_example_count must be one of {ATTACKER_COUNT_MODES}, got {mode!r}")


class SignFlipAttackerClient(AutoencoderClient):
    """Trains normally, then negates and amplifies its own true delta
    before returning it — corrupting the *update*, not the local data.
    """

    def __init__(
        self, *args, amplification: float = 5.0, claimed_num_examples: int | None = None, **kwargs
    ) -> None:
        """Initialize the attacker.

        Args:
            *args: Forwarded to `AutoencoderClient.__init__`.
            amplification: Magnitude multiplier applied to the negated
                true delta (component 5's "negate and amplify").
            claimed_num_examples: Example count to report instead of the
                true one (see module docstring); None reports honestly.
            **kwargs: Forwarded to `AutoencoderClient.__init__`.
        """
        super().__init__(*args, **kwargs)
        self.amplification = amplification
        self.claimed_num_examples = claimed_num_examples

    def fit(
        self, parameters: NDArrays, config: dict[str, Scalar]
    ) -> tuple[NDArrays, int, dict[str, Scalar]]:
        """Train honestly, then return a negated, amplified version of the true delta (and the claimed count)."""
        honest_weights, num_examples, metrics = super().fit(parameters, config)
        corrupted_weights = [
            received - self.amplification * (trained - received)
            for received, trained in zip(parameters, honest_weights)
        ]
        if self.claimed_num_examples is not None:
            num_examples = self.claimed_num_examples
        return corrupted_weights, num_examples, metrics


class StealthAttackerClient(AutoencoderClient):
    """Adaptive attacker that knows the trust filter and stays just inside its tests.

    The filter excludes an update whose cosine similarity to the round's
    consensus is a MAD outlier or below `min_cosine_similarity`, and clips
    norms to a multiple of the median. This attacker estimates the consensus
    as the last aggregate update it can see (this round's global weights minus
    last round's), keeps `cosine_target` cosine similarity to it, and spends the
    rest of its norm budget on the *opposite* of its own honest update's
    component orthogonal to that consensus, so it hides the direction that
    makes its data informative while looking agreeable. Its norm is
    `norm_multiplier` times its honest norm, under the clip. In the first round
    there is no consensus estimate and it behaves honestly.

    A white-box attacker (it knows the filter's rule and thresholds), so a
    stronger test than the sign-flip attacker; it is one adaptive strategy,
    not a proof of robustness against all of them.
    """

    def __init__(
        self,
        *args,
        cosine_target: float = 0.1,
        norm_multiplier: float = 1.5,
        claimed_num_examples: int | None = None,
        **kwargs,
    ) -> None:
        """Initialize the attacker.

        Args:
            *args: Forwarded to `AutoencoderClient.__init__`.
            cosine_target: Cosine similarity to the estimated consensus to aim for.
            norm_multiplier: Crafted update norm as a multiple of the honest one.
            claimed_num_examples: Reported example count; None reports honestly.
            **kwargs: Forwarded to `AutoencoderClient.__init__`.
        """
        super().__init__(*args, **kwargs)
        self.cosine_target = cosine_target
        self.norm_multiplier = norm_multiplier
        self.claimed_num_examples = claimed_num_examples
        self._previous_global: list[np.ndarray] | None = None

    def fit(
        self, parameters: NDArrays, config: dict[str, Scalar]
    ) -> tuple[NDArrays, int, dict[str, Scalar]]:
        """Train honestly, then return received + a crafted delta (see the class docstring)."""
        received = [np.array(p, copy=True) for p in parameters]
        honest_weights, num_examples, metrics = super().fit(parameters, config)
        previous, self._previous_global = self._previous_global, received
        if self.claimed_num_examples is not None:
            num_examples = self.claimed_num_examples
        if previous is None:
            return honest_weights, num_examples, metrics

        flat = lambda arrays: np.concatenate([a.ravel() for a in arrays]).astype(np.float64)  # noqa: E731
        honest_delta = flat(honest_weights) - flat(received)
        consensus = flat(received) - flat(previous)
        consensus_norm, honest_norm = np.linalg.norm(consensus), np.linalg.norm(honest_delta)
        if consensus_norm == 0 or honest_norm == 0:
            return honest_weights, num_examples, metrics
        direction = consensus / consensus_norm
        orthogonal = honest_delta - (honest_delta @ direction) * direction
        orthogonal_norm = np.linalg.norm(orthogonal)
        if orthogonal_norm == 0:
            return honest_weights, num_examples, metrics
        budget = self.norm_multiplier * honest_norm
        crafted = budget * (
            self.cosine_target * direction - np.sqrt(1.0 - self.cosine_target**2) * orthogonal / orthogonal_norm
        )
        out, offset = [], 0
        for r in received:
            out.append((r + crafted[offset : offset + r.size].reshape(r.shape)).astype(r.dtype))
            offset += r.size
        return out, num_examples, metrics
