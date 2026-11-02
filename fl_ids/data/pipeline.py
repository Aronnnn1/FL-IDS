"""Data pipeline (component 1).

Loads the pre-selected `DNN-EdgeIIoT-dataset.csv` (61 engineered features —
the dataset authors already reduced these from the raw 1176; this module
does not redo that feature engineering), drops ID/timestamp/raw-payload
columns, one-hot encodes the remaining nominal categoricals, partitions
samples across simulated clients non-IID via a Dirichlet(alpha) label-skew
split, and — per client, never globally — carves out a held-out benign
validation slice (for autoencoder reconstruction-error thresholding) and a
held-out test slice (for evaluation), then normalizes each client's splits
using a scaler fit only on that client's own training data, with z-scores
clipped (`normalize_with_scaler`).

The column drop list and one-hot categorical column list below are taken
verbatim from the dataset authors' own preprocessing recipe (see
`data/raw/Readme.txt`, "Step 4" and "Step 5"), not independently re-derived —
CLAUDE.md is explicit that this dataset's feature engineering shouldn't be
redone. `Attack_label` is additionally excluded from the feature matrix
(beyond the authors' recipe) because it is fully derivable from the
`Attack_type` target used here (0 iff Attack_type == "Normal"), so keeping
it as a feature would leak the label.

One deliberate departure from the authors' recipe: the "field doesn't
apply" placeholder in the categorical columns is spelled "0" in some
source capture files and "0.0" in others, and the spelling follows the
label -- in the mqtt.* and dns.qry.name.len columns every Normal row says
"0" and every attack row "0.0", so the one-hot column `mqtt.topic_0.0`
alone separates benign from attack with AUROC 1.0. That's an export
artifact, not network behavior, and any model trained on it learns the
file format. `canonicalize_placeholders` collapses both spellings to one
before encoding (see its docstring).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from fl_ids.utils.config import DataConfig

logger = logging.getLogger(__name__)

# Verbatim from the Edge-IIoTset authors' Readme.txt "Step 4": ID/timestamp/
# raw-payload columns that don't generalize across hosts or testbeds.
DEFAULT_DROP_COLUMNS: list[str] = [
    "frame.time",
    "ip.src_host",
    "ip.dst_host",
    "arp.src.proto_ipv4",
    "arp.dst.proto_ipv4",
    "http.file_data",
    "http.request.full_uri",
    "icmp.transmit_timestamp",
    "http.request.uri.query",
    "tcp.options",
    "tcp.payload",
    "tcp.srcport",
    "tcp.dstport",
    "udp.port",
    "mqtt.msg",
]

# Verbatim from the Readme's "Step 5": nominal columns one-hot encoded via
# `encode_text_dummy` (equivalent to pandas `get_dummies`).
CATEGORICAL_COLUMNS: list[str] = [
    "http.request.method",
    "http.referer",
    "http.request.version",
    "dns.qry.name.len",
    "mqtt.conack.flags",
    "mqtt.protoname",
    "mqtt.topic",
]

# Spellings of the categorical columns' "field doesn't apply" placeholder,
# and the one they're all rewritten to. Only these two occur in the dataset.
PLACEHOLDER_SPELLINGS: tuple[str, ...] = ("0", "0.0")
CANONICAL_PLACEHOLDER = "0"

TARGET_COLUMN = "Attack_type"
LEAKY_LABEL_COLUMNS: list[str] = ["Attack_label"]
BENIGN_LABEL = "Normal"


def load_raw_csv(
    csv_path: str | Path, drop_columns: list[str] | None = None
) -> pd.DataFrame:
    """Load the DNN-EdgeIIoT-dataset.csv, excluding dropped columns at parse time.

    Excluding ID/timestamp/raw-payload columns via `usecols` (rather than
    loading then dropping) avoids ever materializing the highest-cardinality
    string columns (e.g. `tcp.payload`, `ip.src_host`) in memory.

    Args:
        csv_path: Path to the CSV file.
        drop_columns: Columns to exclude; defaults to `DEFAULT_DROP_COLUMNS`.

    Returns:
        The loaded DataFrame, with dropped and leaky-label columns absent.
    """
    drop_columns = drop_columns if drop_columns is not None else DEFAULT_DROP_COLUMNS
    excluded = set(drop_columns) | set(LEAKY_LABEL_COLUMNS)
    all_columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
    usecols = [c for c in all_columns if c not in excluded]
    logger.info(
        "Loading %d/%d columns from %s (excluded %d)",
        len(usecols),
        len(all_columns),
        csv_path,
        len(all_columns) - len(usecols),
    )
    return pd.read_csv(csv_path, usecols=usecols, low_memory=False)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop NaN rows and exact-duplicate rows, matching the authors' Step 4.

    Args:
        df: Raw (post-column-drop) DataFrame.

    Returns:
        A cleaned DataFrame with no NaNs and no duplicate rows, index reset.
    """
    return clean_dataframe_with_index(df)[0]


def clean_dataframe_with_index(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """`clean_dataframe`, also returning the positions (in the input) of the rows it kept.

    Args:
        df: Raw (post-column-drop) DataFrame, with a default RangeIndex.

    Returns:
        (cleaned DataFrame with index reset, integer positions of the kept rows in `df`).
    """
    before = len(df)
    df = df.dropna(axis=0, how="any")
    after_na = len(df)
    df = df.drop_duplicates(subset=None, keep="first")
    after_dup = len(df)
    logger.info(
        "Cleaned dataframe: %d -> %d rows (dropped %d NaN, %d duplicate)",
        before,
        after_dup,
        before - after_na,
        after_na - after_dup,
    )
    kept = df.index.to_numpy()
    return df.reset_index(drop=True), kept


def canonicalize_placeholders(
    df: pd.DataFrame, categorical_columns: list[str] | None = None
) -> pd.DataFrame:
    """Rewrite every placeholder spelling in the categorical columns to one canonical value.

    The authors' CSV writes the "field doesn't apply" placeholder as "0" or
    "0.0" depending on which per-attack/per-device capture file a row came
    from, so the spelling encodes the label: in mqtt.topic,
    mqtt.conack.flags, mqtt.protoname and dns.qry.name.len every Normal row
    uses "0" and every attack row "0.0" (no overlap across 2.2M rows).
    Left alone, one-hot encoding turns that into a perfect benign-vs-attack
    feature. Live traffic has no such spelling (tshark reports an absent
    field as empty), so a model leaning on it would also fail in Phase B.

    Must run before `clean_dataframe`, so rows that differed only in
    placeholder spelling are deduplicated together.

    Args:
        df: Raw (post-column-drop) DataFrame.
        categorical_columns: Columns to canonicalize; defaults to
            `CATEGORICAL_COLUMNS`.

    Returns:
        A copy of `df` with every `PLACEHOLDER_SPELLINGS` value in those
        columns replaced by `CANONICAL_PLACEHOLDER`.
    """
    categorical_columns = (
        categorical_columns if categorical_columns is not None else CATEGORICAL_COLUMNS
    )
    df = df.copy()
    for col in categorical_columns:
        if col not in df.columns:
            continue
        as_str = df[col].astype(str)
        is_placeholder = as_str.isin(PLACEHOLDER_SPELLINGS)
        # Only rows that actually hold a value get rewritten; NaN stays NaN
        # for clean_dataframe to drop.
        is_placeholder &= df[col].notna()
        df[col] = df[col].astype(object).where(~is_placeholder, CANONICAL_PLACEHOLDER)
        logger.debug("Canonicalized %d placeholder values in %s", int(is_placeholder.sum()), col)
    return df


def one_hot_encode_categoricals(
    df: pd.DataFrame, categorical_columns: list[str] | None = None
) -> pd.DataFrame:
    """One-hot encode nominal categorical columns, matching the authors' Step 5.

    Encoding is done globally (on the full dataset, before per-client
    partitioning) so every client ends up with an identically-shaped,
    aligned feature space — unlike per-client normalization, a fixed
    category-to-column vocabulary carries no cross-client distributional
    information, so doing this globally does not leak the kind of
    information per-client normalization is meant to protect.

    Args:
        df: DataFrame after cleaning.
        categorical_columns: Columns to one-hot encode; defaults to
            `CATEGORICAL_COLUMNS`.

    Returns:
        DataFrame with categorical columns replaced by one-hot indicator
        columns.
    """
    categorical_columns = (
        categorical_columns if categorical_columns is not None else CATEGORICAL_COLUMNS
    )
    present = [c for c in categorical_columns if c in df.columns]
    return pd.get_dummies(df, columns=present)


def dirichlet_partition(
    labels: np.ndarray, num_clients: int, alpha: float, seed: int
) -> dict[int, np.ndarray]:
    """Partition sample indices across clients via a Dirichlet(alpha) label skew.

    For each class, draws a per-client proportion vector from
    Dirichlet(alpha, ..., alpha) and splits that class's sample indices
    accordingly — the standard non-IID federated partition recipe (Hsu,
    Qi & Brown, 2019). Small alpha (e.g. 0.1) yields a highly skewed,
    non-IID split; large alpha approaches a uniform (IID-like) split.

    Args:
        labels: Integer-encoded class label for every sample.
        num_clients: Number of simulated clients to split across.
        alpha: Dirichlet concentration parameter.
        seed: Random seed, for reproducibility.

    Returns:
        {client_id: array of sample indices assigned to that client}.
    """
    rng = np.random.default_rng(seed)
    client_indices: dict[int, list[int]] = {i: [] for i in range(num_clients)}
    for c in np.unique(labels):
        idx_c = np.where(labels == c)[0]
        rng.shuffle(idx_c)
        proportions = rng.dirichlet(alpha * np.ones(num_clients))
        split_points = (np.cumsum(proportions) * len(idx_c)).astype(int)[:-1]
        for client_id, split in enumerate(np.split(idx_c, split_points)):
            client_indices[client_id].extend(split.tolist())
    return {cid: np.array(idx, dtype=np.int64) for cid, idx in client_indices.items()}


def grouped_fraction_mask(
    y: np.ndarray, groups: np.ndarray, fraction: float, seed: int, min_flows: int, scarce_selected: bool
) -> np.ndarray:
    """Pick whole flows, class by class, until about `fraction` of each class's rows are chosen.

    Args:
        y: Integer class label per row.
        groups: Flow id per row.
        fraction: Share of each class's rows to choose (flows are indivisible, so it is approximate).
        seed: Random seed.
        min_flows: A class with fewer flows than this is "scarce": it cannot be split sensibly.
        scarce_selected: Whether scarce classes are chosen entirely (True) or not at all (False).

    Returns:
        Boolean mask over rows. A flow that would overshoot the target by more than 2x is skipped, unless nothing
        has been chosen yet for the class (then the smallest-overshoot first flow is taken, so a class is never empty).
    """
    rng = np.random.default_rng(seed)
    chosen = np.zeros(len(y), dtype=bool)
    for c in np.unique(y):
        rows = np.where(y == c)[0]
        flows, inverse = np.unique(groups[rows], return_inverse=True)
        sizes = np.bincount(inverse)
        if len(flows) < min_flows:
            chosen[rows] = scarce_selected
            continue
        target = fraction * len(rows)
        take, total = [], 0
        for gi in rng.permutation(len(flows)):
            if total >= target:
                break
            if total > 0 and total + sizes[gi] > 2 * target:
                continue
            take.append(gi)
            total += sizes[gi]
        selected = np.zeros(len(flows), dtype=bool)
        selected[take] = True
        chosen[rows[selected[inverse]]] = True
    return chosen


def grouped_dirichlet_partition(
    y: np.ndarray, groups: np.ndarray, num_clients: int, alpha: float, seed: int
) -> dict[int, np.ndarray]:
    """`dirichlet_partition`, but every flow goes to one client whole.

    Per class, a Dirichlet(alpha) draw gives each client a target share of the class's rows; flows (in random order) are
    handed to the client that is furthest below its target, so shares follow the draw as closely as indivisible flows allow.
    """
    rng = np.random.default_rng(seed)
    client_rows: dict[int, list[np.ndarray]] = {i: [] for i in range(num_clients)}
    for c in np.unique(y):
        rows = np.where(y == c)[0]
        flows, inverse = np.unique(groups[rows], return_inverse=True)
        sizes = np.bincount(inverse)
        target = rng.dirichlet(alpha * np.ones(num_clients)) * len(rows)
        filled = np.zeros(num_clients)
        owner = np.empty(len(flows), dtype=np.int64)
        for gi in rng.permutation(len(flows)):
            k = int(np.argmax(target - filled))
            owner[gi] = k
            filled[k] += sizes[gi]
        row_owner = owner[inverse]
        for k in range(num_clients):
            client_rows[k].append(rows[row_owner == k])
    return {k: (np.concatenate(v) if v else np.empty(0, dtype=np.int64)).astype(np.int64) for k, v in client_rows.items()}


def _pick_flows(rows: np.ndarray, groups: np.ndarray, target: float, rng: np.random.Generator) -> np.ndarray:
    """Boolean mask over `rows`: whole flows (random order) until >= `target` rows, never overshooting by more than 1.5x."""
    if len(rows) == 0 or target <= 0:
        return np.zeros(len(rows), dtype=bool)
    flows, inverse = np.unique(groups[rows], return_inverse=True)
    sizes = np.bincount(inverse)
    take, total = [], 0
    for gi in rng.permutation(len(flows)):
        if total >= target:
            break
        if total + sizes[gi] > 1.5 * target and (total > 0 or sizes[gi] > 3 * target):
            continue
        take.append(gi)
        total += sizes[gi]
    selected = np.zeros(len(flows), dtype=bool)
    selected[take] = True
    return selected[inverse]


def _split_client_data_grouped(
    client_idx: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    benign_class: int,
    val_benign_fraction: float,
    test_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`_split_client_data` with whole flows: (train, val_benign, test) index arrays that share no flow."""
    rng = np.random.default_rng(seed)
    idx = client_idx.copy()
    test_mask = _pick_flows(idx, groups, test_fraction * len(idx), rng)
    test_idx, remaining = idx[test_mask], idx[~test_mask]
    benign_remaining = remaining[y[remaining] == benign_class]
    non_benign_remaining = remaining[y[remaining] != benign_class]
    val_mask = _pick_flows(benign_remaining, groups, val_benign_fraction * len(benign_remaining), rng)
    val_benign_idx, train_benign_idx = benign_remaining[val_mask], benign_remaining[~val_mask]
    return np.concatenate([train_benign_idx, non_benign_remaining]), val_benign_idx, test_idx


def _split_client_data(
    client_idx: np.ndarray,
    y: np.ndarray,
    benign_class: int,
    val_benign_fraction: float,
    test_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Carve one client's indices into (train, val_benign, test) index arrays."""
    rng = np.random.default_rng(seed)
    idx = client_idx.copy()
    rng.shuffle(idx)

    n_test = int(len(idx) * test_fraction)
    test_idx, remaining = idx[:n_test], idx[n_test:]

    benign_mask = y[remaining] == benign_class
    benign_remaining = remaining[benign_mask]
    non_benign_remaining = remaining[~benign_mask]

    n_val_benign = int(len(benign_remaining) * val_benign_fraction)
    val_benign_idx = benign_remaining[:n_val_benign]
    train_benign_idx = benign_remaining[n_val_benign:]

    train_idx = np.concatenate([train_benign_idx, non_benign_remaining])
    return train_idx, val_benign_idx, test_idx


def normalize_with_scaler(
    X_raw: np.ndarray, mean: np.ndarray, scale: np.ndarray, clip: float | None
) -> np.ndarray:
    """Standardize rows with a client's scaler parameters, clipping the z-scores.

    The one normalization every stage uses -- client training, evaluation
    and Phase B live scoring -- so a row is scored the same way wherever it
    appears.

    **Why clip.** Under heavy Dirichlet skew a client's training rows can
    barely vary on a feature (counters such as udp.stream or tcp.seq), so
    its std for that feature is tiny and ordinary rows land 10^3-10^4 std
    out. One such feature's squared error then swamps the other 90 in the
    reconstruction error, making it useless for that client (observed: a
    client whose benign validation loss was ~7,500 while every other
    client's was < 1). A row `clip` std out is already far past any benign
    threshold, so clipping keeps it anomalous without letting it dominate.

    Args:
        X_raw: Raw-scale rows, shape (n_samples, n_features).
        mean: Per-feature mean (`StandardScaler.mean_`).
        scale: Per-feature scale (`StandardScaler.scale_`).
        clip: Clip z-scores to [-clip, clip]; None leaves them unclipped.

    Returns:
        Normalized rows as float32, same shape as `X_raw`.
    """
    X_norm = (X_raw - mean) / scale
    if clip is not None:
        X_norm = np.clip(X_norm, -clip, clip)
    return X_norm.astype(np.float32)


def partition_and_normalize_clients(
    X: np.ndarray,
    y: np.ndarray,
    benign_class: int,
    config: DataConfig,
    seed: int,
    groups: np.ndarray | None = None,
) -> dict[int, dict[str, np.ndarray]]:
    """Partition (X, y) non-IID across clients, then per-client split and normalize.

    Shared by `build_federated_dataset` (real Edge-IIoTset CSV) and the
    synthetic federated dataset builder used for Phase 3's FL-loop tests
    (`fl_ids.data.synthetic.make_synthetic_federated_dataset`) — both need
    the identical Dirichlet-partition -> per-client held-out-slice ->
    per-client-normalize pipeline, just starting from different sources of
    (X, y).

    **Both raw and per-client-normalized features are returned for the
    train/test splits** (`"X"`/`"X_raw"`, `"X_test"`/`"X_test_raw"`) —
    see `fl_ids.models.boosting`'s module docstring for why: the boosting
    classifier (component 2) must always see raw features, never
    per-client-normalized ones. Under real non-IID skew, a client's local
    mean/std can differ from the population's by orders of magnitude
    (e.g. a client that's 94% benign traffic ends up with per-feature
    statistics dominated by benign traffic's characteristic value range),
    which silently destroys a shared model's decision-tree thresholds if
    it's ever evaluated against per-client-normalized input. Phase 5's
    real-data validation caught this directly: the same held-out rows
    scored ~0.94 accuracy in raw features vs. ~0.06 through a
    heavily-skewed client's own scaler. `X_val_benign` doesn't need a raw
    counterpart — component 3 never runs it through boosting, only
    through the autoencoder, which does want normalized input.

    Args:
        X: Full feature matrix, shape (n_samples, n_features).
        y: Integer-encoded class labels, shape (n_samples,).
        benign_class: Integer class index corresponding to the benign class.
        config: Data configuration (num_clients, dirichlet_alpha, split
            fractions, normalize_per_client).
        seed: Global random seed, for reproducible partitioning/splitting.
        groups: Flow id per row. Required when `config.group_by_flow`: flows then stay whole across the partition and
            each client's train/val/test split. Ignored otherwise.

    Returns:
        `{client_id: {"X", "X_raw", "y", "X_val_benign", "y_val_benign",
        "X_test", "X_test_raw", "y_test"}}`, all values `np.ndarray`.
    """
    if config.group_by_flow:
        if groups is None or len(groups) != len(y):
            raise ValueError("data.group_by_flow needs a flow id per row (groups=...)")
        client_index_map = grouped_dirichlet_partition(y, groups, config.num_clients, config.dirichlet_alpha, seed)
    else:
        client_index_map = dirichlet_partition(y, config.num_clients, config.dirichlet_alpha, seed)

    client_data: dict[int, dict[str, np.ndarray]] = {}
    for client_id, client_idx in client_index_map.items():
        if len(client_idx) == 0:
            logger.warning("Client %d received zero samples from the Dirichlet split", client_id)

        if config.group_by_flow:
            train_idx, val_benign_idx, test_idx = _split_client_data_grouped(
                client_idx, y, groups, benign_class, config.val_benign_fraction, config.test_fraction, seed=seed + client_id
            )
        else:
            train_idx, val_benign_idx, test_idx = _split_client_data(
                client_idx,
                y,
                benign_class,
                config.val_benign_fraction,
                config.test_fraction,
                seed=seed + client_id,
            )
        if len(val_benign_idx) == 0:
            logger.warning(
                "Client %d has zero benign validation samples (heavy Dirichlet skew "
                "or too few benign samples in its shard)",
                client_id,
            )

        X_train_raw, X_val_benign_raw, X_test_raw = X[train_idx], X[val_benign_idx], X[test_idx]

        if config.normalize_per_client and len(train_idx) > 0:
            scaler = StandardScaler().fit(X_train_raw)
            clip = config.normalized_clip
            X_train_norm = normalize_with_scaler(X_train_raw, scaler.mean_, scaler.scale_, clip)
            X_val_benign_norm = normalize_with_scaler(X_val_benign_raw, scaler.mean_, scaler.scale_, clip)
            X_test_norm = normalize_with_scaler(X_test_raw, scaler.mean_, scaler.scale_, clip)
        else:
            X_train_norm, X_val_benign_norm, X_test_norm = X_train_raw, X_val_benign_raw, X_test_raw

        client_data[client_id] = {
            "X": X_train_norm.astype(np.float32),
            "X_raw": X_train_raw.astype(np.float32),
            "y": y[train_idx],
            "X_val_benign": X_val_benign_norm.astype(np.float32),
            "y_val_benign": y[val_benign_idx],
            "X_test": X_test_norm.astype(np.float32),
            "X_test_raw": X_test_raw.astype(np.float32),
            "y_test": y[test_idx],
        }

    return client_data


# Bump when fl_ids.data.features changes what it computes, so stale caches are rebuilt.
EXTENDED_FEATURES_VERSION = 2  # 2: the cache also stores each row's flow id (`flow_id`)


def _cache_key(csv_path: str | Path, capture_repairs: dict[str, str] | None) -> str:
    parts = [str(Path(csv_path).resolve()), str(Path(csv_path).stat().st_size), str(int(Path(csv_path).stat().st_mtime))]
    for name, path in sorted((capture_repairs or {}).items()):
        parts += [name, str(Path(path).stat().st_size), str(int(Path(path).stat().st_mtime))]
    return f"v{EXTENDED_FEATURES_VERSION}|" + "|".join(parts)


def load_and_encode(
    csv_path: str | Path,
    capture_repairs: dict[str, str] | None = None,
    extended_features: bool = False,
    cache_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, LabelEncoder, list[str], int]:
    """Load, clean, and encode the raw CSV into a feature matrix and integer labels.

    Shared by `build_federated_dataset` and
    `build_server_and_federated_dataset` — both need the identical
    load/clean/encode steps, just splitting the resulting (X, y)
    differently afterward.

    Args:
        csv_path: Path to `DNN-EdgeIIoT-dataset.csv`.
        capture_repairs: `{attack_type: re-extracted CSV}` — rows of these
            attack types are replaced before cleaning (`data.capture_repairs`,
            see `fl_ids.data.repair`). None or empty loads the CSV as is.
        extended_features: Add the service-port, content and flow features
            (`fl_ids.data.features`, `data.extended_features`): the raw
            payload/URI/port/address/time columns are read to derive them and
            then dropped, so they never become features themselves. Exact
            duplicates are dropped on the extended feature set.
        cache_path: With `extended_features`, an `.npz` to reuse the encoded
            result from (`data.feature_cache`); rebuilt when the CSV, a repair
            file or `EXTENDED_FEATURES_VERSION` changes. None disables caching.

    Returns:
        (X, y, label_encoder, feature_names, benign_class).

    Raises:
        AssertionError: If NaNs remain in the feature matrix after cleaning
            (would indicate a bug in `clean_dataframe`).
    """
    key = _cache_key(csv_path, capture_repairs) if (extended_features and cache_path) else None
    if key and Path(cache_path).exists():
        cached = np.load(cache_path, allow_pickle=False)
        if str(cached["key"]) == key:
            label_encoder = LabelEncoder()
            label_encoder.classes_ = cached["classes"].astype(object)  # same dtype as a freshly fitted encoder
            logger.info("Loaded extended features from cache %s: %s", cache_path, cached["X"].shape)
            return (cached["X"], cached["y"], label_encoder, cached["feature_names"].tolist(),
                    int(cached["benign_class"]))
        logger.info("Feature cache %s is stale; rebuilding", cache_path)

    # Extended features need the raw columns the recipe drops; read them all.
    df = load_raw_csv(csv_path, drop_columns=[] if extended_features else None)
    if capture_repairs:
        from fl_ids.data.repair import apply_capture_repairs  # imports live extraction, which imports this module

        df = apply_capture_repairs(df, capture_repairs)
    df = canonicalize_placeholders(df)
    if extended_features:
        from fl_ids.data.features import derive_features

        from fl_ids.data.features import assign_flows

        df = df.reset_index(drop=True)
        derived = derive_features(df)
        flow_ids = assign_flows(df)  # per packet, before rows are dropped; same call derive_features makes
        df = df.drop(columns=[c for c in DEFAULT_DROP_COLUMNS if c in df.columns])
        df = pd.concat([df, derived], axis=1)
    else:
        flow_ids = None
    df, kept = clean_dataframe_with_index(df)
    if flow_ids is not None:
        flow_ids = flow_ids[kept]
    df = one_hot_encode_categoricals(df)

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[TARGET_COLUMN].values)
    benign_class = int(label_encoder.transform([BENIGN_LABEL])[0])

    feature_df = df.drop(columns=[TARGET_COLUMN])
    feature_names = feature_df.columns.tolist()
    X = feature_df.to_numpy(dtype=np.float32)

    assert not np.isnan(X).any(), "NaNs present in feature matrix after cleaning"

    if key:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_path, key=np.array(key), X=X, y=y, classes=np.asarray(label_encoder.classes_).astype(str),
                 feature_names=np.array(feature_names), benign_class=np.array(benign_class), flow_id=flow_ids)
        logger.info("Wrote feature cache %s", cache_path)

    return X, y, label_encoder, feature_names, benign_class


def load_flow_ids(
    csv_path: str | Path, capture_repairs: dict[str, str] | None, cache_path: str | Path
) -> np.ndarray:
    """Flow (connection) id of every row of the matrix `load_and_encode` returns, from its feature cache.

    Packets of one connection share these flow-level features, so splits that must not put siblings on both sides
    (calibration vs. client test slices) group on this id.

    Raises:
        FileNotFoundError / ValueError: If the cache is missing, stale or was built without flow ids (call
            `load_and_encode` with `extended_features=True` and this `cache_path` first).
    """
    if not Path(cache_path).exists():
        raise FileNotFoundError(f"{cache_path}: run load_and_encode with extended_features=True first")
    cached = np.load(cache_path, allow_pickle=False)
    if str(cached["key"]) != _cache_key(csv_path, capture_repairs) or "flow_id" not in cached.files:
        raise ValueError(f"{cache_path} is stale or has no flow ids; rebuild it with load_and_encode")
    return cached["flow_id"]


def server_pool_split(
    X: np.ndarray,
    y: np.ndarray,
    config: "Config",
    seed: int,
    pool_cap: int | None,
    excluded_classes: frozenset[int] = frozenset(),
    groups: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
    """The server calibration split and the federated pool, row-level or by flow depending on `config.data.group_by_flow`.

    Returns:
        (X_calib, y_calib, X_pool, y_pool, groups_calib, groups_pool); the group arrays are None for row-level splits.
        `groups` (flow id per row) is read from the feature cache when not given. `pool_cap` rows (stratified by class;
        None or <= 0 = no cap) are kept in the pool. `excluded_classes` are removed
        from both sides (the zero-day experiment).
    """
    from sklearn.model_selection import train_test_split

    frac = config.boosting.calibration_fraction
    if config.data.group_by_flow:
        if groups is None:
            groups = load_flow_ids(config.data.dnn_csv_path, config.data.capture_repairs, config.data.feature_cache)
        if len(groups) != len(y):
            raise ValueError("flow ids do not match the feature matrix; rebuild the feature cache")
        mask = grouped_fraction_mask(y, groups, frac, seed, config.data.min_flows_per_class, scarce_selected=True)
        X_calib, y_calib, g_calib = X[mask], y[mask], groups[mask]
        X_pool, y_pool, g_pool = X[~mask], y[~mask], groups[~mask]
        if pool_cap and pool_cap > 0 and len(y_pool) > pool_cap:
            keep = grouped_fraction_mask(y_pool, g_pool, pool_cap / len(y_pool), seed, config.data.min_flows_per_class, scarce_selected=False)
            X_pool, y_pool, g_pool = X_pool[keep], y_pool[keep], g_pool[keep]
    else:
        X_calib, X_pool, y_calib, y_pool = train_test_split(X, y, train_size=frac, random_state=seed, stratify=y)
        g_calib = g_pool = None
        if pool_cap and pool_cap > 0 and len(X_pool) > pool_cap:
            X_pool, _, y_pool, _ = train_test_split(X_pool, y_pool, train_size=pool_cap, random_state=seed, stratify=y_pool)
    if excluded_classes:
        excluded = np.array(sorted(excluded_classes))
        ck, pk = ~np.isin(y_calib, excluded), ~np.isin(y_pool, excluded)
        X_calib, y_calib, X_pool, y_pool = X_calib[ck], y_calib[ck], X_pool[pk], y_pool[pk]
        if g_calib is not None:
            g_calib, g_pool = g_calib[ck], g_pool[pk]
    return X_calib, y_calib, X_pool, y_pool, g_calib, g_pool


def calibration_eval_split(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray | None, config: "Config", seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Hold back `boosting.calibration_eval_fraction` of the calibration set to score each boosting version (by flow when grouped)."""
    from sklearn.model_selection import train_test_split

    frac = config.boosting.calibration_eval_fraction
    if config.data.group_by_flow and groups is not None:
        mask = grouped_fraction_mask(y, groups, frac, seed, config.data.min_flows_per_class, scarce_selected=False)
        return X[~mask], X[mask], y[~mask], y[mask]
    return train_test_split(X, y, test_size=frac, random_state=seed, stratify=y)


def build_federated_dataset(
    csv_path: str | Path,
    config: DataConfig,
    seed: int,
) -> tuple[dict[int, dict[str, np.ndarray]], LabelEncoder, list[str]]:
    """Build the full per-client federated dataset (component 1's main entrypoint).

    Args:
        csv_path: Path to `DNN-EdgeIIoT-dataset.csv`.
        config: Data configuration (num_clients, dirichlet_alpha, split
            fractions, normalize_per_client).
        seed: Global random seed, for reproducible partitioning/splitting.

    Returns:
        A tuple of:
        - `{client_id: {"X", "y", "X_val_benign", "y_val_benign", "X_test",
          "y_test"}}`, all values `np.ndarray`.
        - The fitted `LabelEncoder` mapping `Attack_type` strings to the
          integer classes used in `y`.
        - The list of feature column names, in `X` column order.
    """
    X, y, label_encoder, feature_names, benign_class = load_and_encode(csv_path, config.capture_repairs, config.extended_features, config.feature_cache)
    client_data = partition_and_normalize_clients(X, y, benign_class, config, seed)
    return client_data, label_encoder, feature_names


def build_server_and_federated_dataset(
    csv_path: str | Path,
    config: DataConfig,
    calibration_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict[int, dict[str, np.ndarray]], LabelEncoder, list[str]]:
    """Build a server-held calibration set plus the per-client federated dataset.

    Per component 2's label-source design decision (see
    `fl_ids.models.boosting`'s module docstring), the boosting classifier's
    training labels come from a small, independently server-held
    calibration set — never from client data. That means this calibration
    slice must be carved out of the full dataset *before* client
    partitioning and kept disjoint from every client's data, not
    reconstructed after the fact from what clients happen to hold.

    Args:
        csv_path: Path to `DNN-EdgeIIoT-dataset.csv`.
        config: Data configuration (num_clients, dirichlet_alpha, split
            fractions, normalize_per_client) — applied to the *remainder*
            after the calibration slice is removed.
        calibration_fraction: Fraction of the full cleaned dataset held out
            server-side (stratified by class), matching
            `BoostingConfig.calibration_fraction`.
        seed: Global random seed, for reproducible splitting/partitioning.

    Returns:
        (X_calibration, y_calibration, client_data, label_encoder, feature_names).
        `X_calibration` is raw-scale (not normalized) — the caller
        standardizes it however the boosting model expects (see
        `fl_ids.models.boosting`'s feature-scale design decision).
    """
    X, y, label_encoder, feature_names, benign_class = load_and_encode(csv_path, config.capture_repairs, config.extended_features, config.feature_cache)

    X_calib, X_pool, y_calib, y_pool = train_test_split(
        X, y, train_size=calibration_fraction, random_state=seed, stratify=y
    )

    client_data = partition_and_normalize_clients(X_pool, y_pool, benign_class, config, seed)
    return X_calib, y_calib, client_data, label_encoder, feature_names
