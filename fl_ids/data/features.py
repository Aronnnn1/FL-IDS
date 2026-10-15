"""Service-port, content and flow features (the "extended" feature set).

The 91 base features describe each packet on its own. In the HTTP-family
attacks (SQL_injection, XSS, Uploading, Password) only ~5-17% of packets carry
any HTTP content; the rest are bare TCP handshake/ACK packets to port 80 on the
same server, identical whichever attack produced them (2.31% of rows share a
91-feature vector with a row of another class). This module derives the
information that separates them, from columns the dataset recipe drops:

  svc_port  the server side of a connection: the smallest port below the
            Linux ephemeral range, or -1 (ICMP/ARP). Ephemeral client ports
            are never used -- their ranges follow capture time, i.e. the label.
  c_*       per-packet content: decoded payload length, entropy, printable
            share, HTTP request flag and status code, header counts, URI
            length/parameters/%-encoding, file-data length, special
            characters, and counts of six generic signature groups.
  f_*       per-flow aggregates. Packets are grouped by (IP pair, protocol,
            port pair) in capture order; a new flow starts after a 60 s idle
            gap or once the flow has been active 120 s (CICFlowMeter's
            default active timeout). Every packet gets its flow's totals.

IP addresses, timestamps, ephemeral ports and row order are used only to
*group* packets into flows, never as features: each identifies the source
capture, and so the label.

The same `derive_features` runs on the dataset CSV (fl_ids.data.pipeline) and
on live tshark output (fl_ids.sdn.feature_extraction), so live rows get the
same features as training rows. Measured effect and caveats: PAPER_NOTES.md
section 8.10.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from urllib.parse import unquote

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EPHEMERAL_PORT_MIN = 32768  # Linux default ephemeral range start
FLOW_IDLE_TIMEOUT_S = 60.0
FLOW_ACTIVE_TIMEOUT_S = 120.0
_ENTROPY_PREFIX_BYTES = 2048

KEYWORD_GROUPS: dict[str, str] = {
    "sql": r"select|union|sleep\(|benchmark\(|pg_sleep|dbms_pipe|waitfor|information_schema|"
    r"\bor\s+\d+=\d+|\band\s+\d+=\d+|'\s*or\s|--\s|/\*|char\(|concat\(|order\s+by",
    "xss": r"<script|javascript:|onerror|onload|onmouseover|alert\(|<img|<svg|<iframe|document\.cookie|eval\(",
    "upload": r"multipart/form-data|content-disposition|filename=|<\?php|\.php\b",
    "auth": r"login|password|passwd|username|user=|pass=|authorization:",
    "trav": r"\.\./|/etc/passwd|cmd=|exec\(|system\(|wget\s|curl\s|/bin/",
    "tool": r"nikto|nmap|sqlmap|acunetix|nessus|dirbuster|wpscan|masscan|zgrab|gobuster|hydra",
}
_KEYWORD_RE = {k: re.compile(v) for k, v in KEYWORD_GROUPS.items()}
_HTTP_REQUEST_RE = re.compile(r"^(get|post|put|head|delete|options|trace|patch|connect) ")
_HTTP_STATUS_RE = re.compile(r"^http/1\.[01] (\d{3})")
_TIME_OF_DAY_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)")
_SPECIAL_CHARS = set("'\"<>;%()=&")
_PLACEHOLDERS = {"", "0", "0.0", "nan", "None"}

# Columns this module reads; callers loading the CSV must not drop them first.
REQUIRED_COLUMNS: list[str] = [
    "frame.time", "ip.src_host", "ip.dst_host", "tcp.srcport", "tcp.dstport", "udp.port",
    "tcp.payload", "http.request.full_uri", "http.file_data",
    "tcp.connection.syn", "tcp.connection.fin", "tcp.connection.rst",
]


def _text(series: pd.Series) -> list[str]:
    values = series.fillna("").astype(str).tolist()
    return ["" if v.strip() in _PLACEHOLDERS else v for v in values]


def _decode_hex_payload(h: str) -> str:
    """Hex payload -> lowercase latin-1 text. Accepts the CSV's plain hex and tshark's colon-separated hex."""
    if not h:
        return ""
    try:
        return bytes.fromhex(h.replace(":", "")).decode("latin-1").lower()
    except ValueError:
        return ""


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    return -sum(c / n * math.log2(c / n) for c in Counter(text).values())


def _to_float(series: pd.Series) -> np.ndarray:
    """Numeric column -> floats; tshark 4.x's True/False and hex both handled, anything else 0."""
    fast = pd.to_numeric(series, errors="coerce")
    odd = fast.isna() & series.notna()
    if not odd.any():
        return fast.fillna(0.0).to_numpy(dtype=np.float64)

    def conv(v):
        if pd.isna(v):
            return 0.0
        s = str(v).strip()
        if s in ("True", "False"):
            return 1.0 if s == "True" else 0.0
        if s.startswith("0x"):
            try:
                return float(int(s, 16))
            except ValueError:
                return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0
    out = fast.fillna(0.0).to_numpy(dtype=np.float64).copy()
    out[odd.to_numpy()] = [conv(v) for v in series[odd].tolist()]
    return out


def content_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-packet content features (`c_*`) from tcp.payload, http.request.full_uri and http.file_data."""
    payload = [_decode_hex_payload(h) for h in _text(df["tcp.payload"])]
    uri_raw = _text(df["http.request.full_uri"])
    uri = [unquote(u).lower() if u else "" for u in uri_raw]
    fdata = [f.lower() for f in _text(df["http.file_data"])]

    out = pd.DataFrame(index=df.index)
    out["c_pl_len"] = [len(t) for t in payload]
    out["c_pl_entropy"] = [_entropy(t[:_ENTROPY_PREFIX_BYTES]) for t in payload]
    out["c_pl_printable"] = [
        (sum(32 <= ord(ch) < 127 for ch in t[:_ENTROPY_PREFIX_BYTES]) / min(len(t), _ENTROPY_PREFIX_BYTES)) if t else 0.0
        for t in payload
    ]
    out["c_http_req"] = [1 if _HTTP_REQUEST_RE.match(t) else 0 for t in payload]
    out["c_http_status"] = [int(m.group(1)) if (m := _HTTP_STATUS_RE.match(t)) else 0 for t in payload]
    out["c_n_headers"] = [t.count("\r\n") for t in payload]
    out["c_n_xheaders"] = [t.count("\r\nx-") for t in payload]
    out["c_uri_len"] = [len(u) for u in uri]
    out["c_uri_nparams"] = [u.count("&") + 1 if "?" in u else 0 for u in uri]
    out["c_uri_pct"] = [u.count("%") for u in uri_raw]
    out["c_fd_len"] = [len(f) for f in fdata]
    combined = [a + " " + b + " " + c for a, b, c in zip(payload, uri, fdata)]
    out["c_special"] = [sum(ch in _SPECIAL_CHARS for ch in t) for t in combined]
    for name, rx in _KEYWORD_RE.items():
        out[f"c_kw_{name}"] = [len(rx.findall(t)) if len(t) > 2 else 0 for t in combined]
    return out


def service_port(df: pd.DataFrame) -> np.ndarray:
    """Server-side port of each packet's connection: smallest port below the ephemeral range, else -1."""
    ports = np.stack([_to_float(df["tcp.srcport"]), _to_float(df["tcp.dstport"]), _to_float(df["udp.port"])], axis=1)
    ports = np.where((ports > 0) & (ports < EPHEMERAL_PORT_MIN), ports, np.inf)
    svc = ports.min(axis=1)
    return np.where(np.isfinite(svc), svc, -1.0)


def time_of_day_seconds(series: pd.Series) -> np.ndarray:
    """Seconds since midnight from a frame.time string (used only to segment flows).

    Works on the dataset's ' 2021 11:44:10.081753000 ' and on tshark's
    'Nov 29, 2021 11:44:10.081753000 IST'. Unparseable -> -1.
    """
    out = np.full(len(series), -1.0)
    for i, s in enumerate(series.fillna("").astype(str).tolist()):
        m = _TIME_OF_DAY_RE.search(s)
        if m:
            out[i] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return out


def assign_flows(df: pd.DataFrame) -> np.ndarray:
    """Flow id per packet: same (IP pair, protocol, port pair), in row order, split on idle/active timeouts."""
    tod = time_of_day_seconds(df["frame.time"])
    src = df["ip.src_host"].fillna("").astype(str).to_numpy()
    dst = df["ip.dst_host"].fillna("").astype(str).to_numpy()
    lo_ip = np.where(src < dst, src, dst)
    hi_ip = np.where(src < dst, dst, src)
    sp, dp, up = _to_float(df["tcp.srcport"]), _to_float(df["tcp.dstport"]), _to_float(df["udp.port"])
    proto = np.where(sp + dp > 0, "t", np.where(up > 0, "u", "o"))
    key = pd.Series(lo_ip) + "|" + hi_ip + "|" + proto + "|" + \
        np.minimum(sp, dp).astype(int).astype(str) + "|" + np.maximum(sp, dp).astype(int).astype(str)
    key_codes = pd.factorize(key)[0]

    seg = np.zeros(len(df), dtype=np.int64)
    last_t: dict[int, float] = {}
    start_t: dict[int, float] = {}
    current: dict[int, int] = {}
    for i, (k, t) in enumerate(zip(key_codes.tolist(), tod.tolist())):
        if (k not in current or abs(t - last_t[k]) > FLOW_IDLE_TIMEOUT_S
                or abs(t - start_t[k]) > FLOW_ACTIVE_TIMEOUT_S):
            current[k] = current.get(k, -1) + 1
            start_t[k] = t
        last_t[k] = t
        seg[i] = current[k]
    return pd.factorize(pd.Series(key_codes).astype(str) + "#" + pd.Series(seg).astype(str))[0]


def flow_features(df: pd.DataFrame, content: pd.DataFrame, flow_id: np.ndarray) -> pd.DataFrame:
    """Per-flow aggregates (`f_*`), broadcast back to every packet of the flow."""
    g = pd.DataFrame({
        "fid": flow_id,
        "t": time_of_day_seconds(df["frame.time"]),
        "pl": content["c_pl_len"].to_numpy(),
        "req": content["c_http_req"].to_numpy(),
        "status": content["c_http_status"].to_numpy(),
        "xh": content["c_n_xheaders"].to_numpy(),
        "syn": _to_float(df["tcp.connection.syn"]),
        "fin": _to_float(df["tcp.connection.fin"]),
        "rst": _to_float(df["tcp.connection.rst"]),
        "ent": content["c_pl_entropy"].to_numpy(),
        "uri": content["c_uri_len"].to_numpy(),
        **{f"kw_{k}": content[f"c_kw_{k}"].to_numpy() for k in KEYWORD_GROUPS},
    })
    g["pl_nz"] = (g["pl"] > 0).astype(float)
    agg = g.groupby("fid").agg(
        f_npkts=("t", "size"),
        f_tmin=("t", "min"),
        f_tmax=("t", "max"),
        f_pl_sum=("pl", "sum"),
        f_pl_max=("pl", "max"),
        f_pl_nonzero=("pl_nz", "mean"),
        f_req=("req", "sum"),
        f_status_max=("status", "max"),
        f_xh_max=("xh", "max"),
        f_syn=("syn", "sum"),
        f_fin=("fin", "sum"),
        f_rst=("rst", "sum"),
        f_ent_max=("ent", "max"),
        f_uri_max=("uri", "max"),
        **{f"f_kw_{k}": (f"kw_{k}", "sum") for k in KEYWORD_GROUPS},
    )
    agg["f_dur"] = (agg.pop("f_tmax") - agg.pop("f_tmin")).clip(lower=0)
    agg["f_pps"] = agg["f_npkts"] / (agg["f_dur"] + 1e-3)
    out = agg.loc[flow_id].reset_index(drop=True)
    out.index = df.index
    return out


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """All extended features for raw rows (dataset CSV or live tshark), aligned to `df.index`.

    Args:
        df: Raw rows in capture order, containing `REQUIRED_COLUMNS`.

    Returns:
        DataFrame with `svc_port`, the `c_*` content features and the `f_*`
        flow features (39 columns), all numeric.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"derive_features needs columns that were dropped or not extracted: {missing}")
    content = content_features(df)
    flow_id = assign_flows(df)
    flows = flow_features(df, content, flow_id)
    logger.info("Derived extended features: %d packets in %d flows", len(df), int(flow_id.max()) + 1 if len(df) else 0)
    out = pd.concat([content, flows], axis=1)
    out.insert(0, "svc_port", service_port(df))
    return out
