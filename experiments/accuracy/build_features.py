"""Build candidate feature groups for the accuracy experiments.

Reads the raw Edge-IIoTset CSV with every column, applies the project's own
MITM repair and placeholder canonicalization, then derives three groups of
candidate features on top of the project's 47 base columns:

  svc_*   the service-side port of a connection (well-known / server port only;
          ephemeral client ports follow capture time and would leak the label)
  c_*     per-packet content features from tcp.payload / URI / file_data
          (lengths, entropy, HTTP request/response flags, status code, and
          generic attack-signature keyword counts)
  f_*     per-flow aggregates: packets of one connection share them, so a
          content-less ACK inherits what its connection carried

Never used as features: IP addresses, absolute time, ephemeral ports, row
order. IPs, ports and time are used only to *group* packets into flows, the
way a flow meter does on a live capture.

Output: experiments/accuracy/features.parquet (one row per CSV row, before
dedup; dedup happens per feature set at training time).
"""

from __future__ import annotations

import logging
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fl_ids.data.pipeline import (  # noqa: E402
    DEFAULT_DROP_COLUMNS,
    LEAKY_LABEL_COLUMNS,
    TARGET_COLUMN,
    canonicalize_placeholders,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("build_features")

CSV = "data/raw/DNN-EdgeIIoT-dataset.csv"
MITM_CSV = "data/processed/MITM_reextracted.csv"
OUT = Path("experiments/accuracy/features.parquet")

EPHEMERAL_MIN = 32768  # Linux default ephemeral range start
FLOW_GAP_SECONDS = 60.0  # idle timeout: a gap this long starts a new flow
FLOW_ACTIVE_TIMEOUT = 120.0  # active timeout (CICFlowMeter's default): long sessions are cut into records

KEYWORDS = {
    "sql": r"select|union|sleep\(|benchmark\(|pg_sleep|dbms_pipe|waitfor|information_schema|"
    r"\bor\s+\d+=\d+|\band\s+\d+=\d+|'\s*or\s|--\s|/\*|char\(|concat\(|order\s+by",
    "xss": r"<script|javascript:|onerror|onload|onmouseover|alert\(|<img|<svg|<iframe|document\.cookie|eval\(",
    "upload": r"multipart/form-data|content-disposition|filename=|<\?php|\.php\b",
    "auth": r"login|password|passwd|username|user=|pass=|authorization:",
    "trav": r"\.\./|/etc/passwd|cmd=|exec\(|system\(|wget\s|curl\s|/bin/",
    "tool": r"nikto|nmap|sqlmap|acunetix|nessus|dirbuster|wpscan|masscan|zgrab|gobuster|hydra",
}
KW_RE = {k: re.compile(v) for k, v in KEYWORDS.items()}
HTTP_REQ_RE = re.compile(r"^(get|post|put|head|delete|options|trace|patch|connect) ")
STATUS_RE = re.compile(r"^http/1\.[01] (\d{3})")
SPECIAL = set("'\"<>;%()=&")


def is_placeholder(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).isin(["0", "0.0", "", "nan"])


def decode_payload(h: str) -> str:
    try:
        return bytes.fromhex(h).decode("latin-1").lower()
    except ValueError:
        return ""


def entropy(b: str) -> float:
    if not b:
        return 0.0
    n = len(b)
    return -sum(c / n * math.log2(c / n) for c in Counter(b).values())


def content_features(df: pd.DataFrame) -> pd.DataFrame:
    t0 = time.time()
    payload = df["tcp.payload"].astype(str).where(~is_placeholder(df["tcp.payload"]), "")
    uri = df["http.request.full_uri"].astype(str).where(~is_placeholder(df["http.request.full_uri"]), "")
    fdata = df["http.file_data"].astype(str).where(~is_placeholder(df["http.file_data"]), "")

    text_pl = [decode_payload(h) if h else "" for h in payload.tolist()]
    text_uri = [unquote(u).lower() if u else "" for u in uri.tolist()]
    text_fd = [f.lower() if f else "" for f in fdata.tolist()]
    log.info("decoded content in %.1fs", time.time() - t0)

    out = pd.DataFrame(index=df.index)
    out["c_pl_len"] = [len(t) for t in text_pl]
    out["c_pl_entropy"] = [entropy(t[:2048]) for t in text_pl]
    out["c_pl_printable"] = [
        (sum(32 <= ord(ch) < 127 for ch in t[:2048]) / min(len(t), 2048)) if t else 0.0 for t in text_pl
    ]
    out["c_http_req"] = [1 if HTTP_REQ_RE.match(t) else 0 for t in text_pl]
    out["c_http_status"] = [int(m.group(1)) if (m := STATUS_RE.match(t)) else 0 for t in text_pl]
    out["c_n_headers"] = [t.count("\r\n") if t else 0 for t in text_pl]
    out["c_n_xheaders"] = [t.count("\r\nx-") if t else 0 for t in text_pl]
    out["c_uri_len"] = [len(u) for u in text_uri]
    out["c_uri_nparams"] = [u.count("&") + 1 if "?" in u else 0 for u in text_uri]
    out["c_uri_pct"] = [u.count("%") for u in uri.tolist()]
    out["c_fd_len"] = [len(f) for f in text_fd]
    combined = [a + " " + b + " " + c for a, b, c in zip(text_pl, text_uri, text_fd)]
    out["c_special"] = [sum(ch in SPECIAL for ch in t) for t in combined]
    for k, rx in KW_RE.items():
        out[f"c_kw_{k}"] = [len(rx.findall(t)) if len(t) > 2 else 0 for t in combined]
    log.info("content features in %.1fs", time.time() - t0)
    return out


def to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def service_port(df: pd.DataFrame) -> pd.Series:
    sp, dp, up = to_float(df["tcp.srcport"]), to_float(df["tcp.dstport"]), to_float(df["udp.port"])
    ports = np.stack([sp.values, dp.values, up.values], axis=1)
    ports = np.where((ports > 0) & (ports < EPHEMERAL_MIN), ports, np.inf)
    svc = ports.min(axis=1)
    return pd.Series(np.where(np.isfinite(svc), svc, -1.0), index=df.index)


def time_of_day(s: pd.Series) -> np.ndarray:
    # ' 2021 11:44:10.081753000 ' -> seconds since midnight (grouping only)
    parts = s.astype(str).str.strip().str.split(" ").str[-1].str.split(":", expand=True)
    h, m, sec = (pd.to_numeric(parts[i], errors="coerce") for i in range(3))
    return (h * 3600 + m * 60 + sec).fillna(-1).to_numpy()


def flow_features(df: pd.DataFrame, content: pd.DataFrame, svc: pd.Series) -> pd.DataFrame:
    t0 = time.time()
    tod = time_of_day(df["frame.time"])
    src, dst = df["ip.src_host"].astype(str), df["ip.dst_host"].astype(str)
    a = np.where(src < dst, src, dst)
    b = np.where(src < dst, dst, src)
    sp, dp = to_float(df["tcp.srcport"]).values, to_float(df["tcp.dstport"]).values
    p_lo, p_hi = np.minimum(sp, dp), np.maximum(sp, dp)
    proto = np.where(sp + dp > 0, "t", np.where(to_float(df["udp.port"]).values > 0, "u", "o"))
    key = pd.Series(a, index=df.index) + "|" + b + "|" + proto + "|" + p_lo.astype(int).astype(str) + "|" + p_hi.astype(int).astype(str)

    # Segment each key into flows: in row (capture) order, a new flow starts
    # when the time-of-day gap to the key's previous packet exceeds the gap.
    order = np.arange(len(df))
    kdf = pd.DataFrame({"key": key.values, "t": tod, "i": order})
    # Idle timeout (gap) and active timeout (record length), in row order per key.
    key_codes = pd.factorize(kdf["key"])[0]
    seg = np.zeros(len(kdf), dtype=np.int64)
    last_t, start_t, cur = {}, {}, {}
    for i, (k, t) in enumerate(zip(key_codes.tolist(), tod.tolist())):
        if k not in cur or abs(t - last_t[k]) > FLOW_GAP_SECONDS or abs(t - start_t[k]) > FLOW_ACTIVE_TIMEOUT:
            cur[k] = cur.get(k, -1) + 1
            start_t[k] = t
        last_t[k] = t
        seg[i] = cur[k]
    flow_id = pd.factorize(pd.Series(key_codes).astype(str) + "#" + pd.Series(seg).astype(str))[0]
    log.info("%d flows from %d packets (%.1fs)", flow_id.max() + 1, len(df), time.time() - t0)

    g = pd.DataFrame(
        {
            "fid": flow_id,
            "t": tod,
            "pl": content["c_pl_len"].values,
            "req": content["c_http_req"].values,
            "status": content["c_http_status"].values,
            "xh": content["c_n_xheaders"].values,
            "syn": to_float(df["tcp.connection.syn"]).values,
            "fin": to_float(df["tcp.connection.fin"]).values,
            "rst": to_float(df["tcp.connection.rst"]).values,
            "ent": content["c_pl_entropy"].values,
            "uri": content["c_uri_len"].values,
            **{f"kw_{k}": content[f"c_kw_{k}"].values for k in KEYWORDS},
        }
    )
    agg = g.groupby("fid").agg(
        f_npkts=("t", "size"),
        f_tmin=("t", "min"),
        f_tmax=("t", "max"),
        f_pl_sum=("pl", "sum"),
        f_pl_max=("pl", "max"),
        f_pl_nonzero=("pl", lambda x: float((x > 0).mean())),
        f_req=("req", "sum"),
        f_status_max=("status", "max"),
        f_xh_max=("xh", "max"),
        f_syn=("syn", "sum"),
        f_fin=("fin", "sum"),
        f_rst=("rst", "sum"),
        f_ent_max=("ent", "max"),
        f_uri_max=("uri", "max"),
        **{f"f_kw_{k}": (f"kw_{k}", "sum") for k in KEYWORDS},
    )
    agg["f_dur"] = (agg.pop("f_tmax") - agg.pop("f_tmin")).clip(lower=0)
    agg["f_pps"] = agg["f_npkts"] / (agg["f_dur"] + 1e-3)
    out = agg.loc[flow_id].reset_index(drop=True)
    out.index = df.index
    out["flow_id"] = flow_id  # for grouped splits only, never a feature
    log.info("flow features in %.1fs", time.time() - t0)
    return out


def main() -> None:
    t0 = time.time()
    df = pd.read_csv(CSV, low_memory=False)
    log.info("loaded %d rows x %d cols", *df.shape)
    mitm = pd.read_csv(MITM_CSV, low_memory=False)
    removed = int((df[TARGET_COLUMN] == "MITM").sum())
    df = pd.concat([df[df[TARGET_COLUMN] != "MITM"], mitm[df.columns]], ignore_index=True)
    log.info("MITM repair: %d -> %d rows", removed, len(mitm))
    df = canonicalize_placeholders(df)
    df = df.dropna(axis=0, how="any").reset_index(drop=True)

    content = content_features(df)
    svc = service_port(df)
    flows = flow_features(df, content, svc)

    base_cols = [c for c in df.columns if c not in set(DEFAULT_DROP_COLUMNS) | set(LEAKY_LABEL_COLUMNS)]
    out = pd.concat([df[base_cols], content, flows], axis=1)
    out["svc_port"] = svc.values
    for c in base_cols:
        if out[c].dtype == object:
            out[c] = out[c].astype(str)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    log.info("wrote %s %s in %.0fs", OUT, out.shape, time.time() - t0)


if __name__ == "__main__":
    main()
