"""Service-port, content and flow features (fl_ids.data.features), and their use by the loader and boosting."""

import numpy as np
import pandas as pd
import pytest

from fl_ids.data.features import (
    KEYWORD_GROUPS,
    assign_flows,
    content_features,
    derive_features,
    service_port,
    time_of_day_seconds,
)
from fl_ids.data.pipeline import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, load_and_encode

SQLI_REQUEST = "GET /dvwa/?id=1' or 1=1-- &Submit=Submit HTTP/1.1\r\nHost: x\r\n\r\n"


def _hex(text: str) -> str:
    return text.encode("latin-1").hex()


def _row(time="2021 10:00:00.0", src="10.0.0.1", dst="10.0.0.2", sport="52764.0", dport="80.0", udp="0",
         payload="0", uri="0", fdata="0", syn="0", fin="0", rst="0"):
    return {"frame.time": f" {time} ", "ip.src_host": src, "ip.dst_host": dst, "tcp.srcport": sport,
            "tcp.dstport": dport, "udp.port": udp, "tcp.payload": payload, "http.request.full_uri": uri,
            "http.file_data": fdata, "tcp.connection.syn": syn, "tcp.connection.fin": fin, "tcp.connection.rst": rst}


def test_service_port_is_the_server_side_never_the_ephemeral_port():
    df = pd.DataFrame([_row(sport="52764.0", dport="1883.0"), _row(sport="80.0", dport="40001.0"),
                       _row(sport="0", dport="0", udp="53.0"), _row(sport="0", dport="0")])
    assert service_port(df).tolist() == [1883.0, 80.0, 53.0, -1.0]


def test_content_features_read_csv_hex_and_tshark_colon_hex_identically():
    plain = _hex(SQLI_REQUEST)
    colon = ":".join(plain[i:i + 2] for i in range(0, len(plain), 2))
    out = content_features(pd.DataFrame([_row(payload=plain), _row(payload=colon), _row()]))
    assert out.iloc[0].equals(out.iloc[1])
    assert out.loc[0, "c_http_req"] == 1 and out.loc[0, "c_kw_sql"] >= 1 and out.loc[0, "c_pl_len"] == len(SQLI_REQUEST)
    assert (out.loc[2] == 0).all()  # placeholder payload -> no content


def test_time_of_day_parses_dataset_and_tshark_formats():
    t = time_of_day_seconds(pd.Series([" 2021 11:44:10.5 ", "Nov 29, 2021 11:44:10.500000000 IST", "junk"]))
    assert t.tolist() == [42250.5, 42250.5, -1.0]


def test_flows_split_on_idle_and_active_timeouts():
    rows = [_row(time="2021 10:00:00"), _row(time="2021 10:00:30", src="10.0.0.2", dst="10.0.0.1",
                                             sport="80.0", dport="52764.0"),   # reply: same flow
            _row(time="2021 10:01:45"),                                      # 75 s idle: new flow
            _row(time="2021 10:02:30"), _row(time="2021 10:03:20"), _row(time="2021 10:04:10"),  # active > 120 s: split
            _row(time="2021 10:00:10", sport="52999.0")]                    # other port pair: other flow
    fid = assign_flows(pd.DataFrame(rows))
    assert fid[0] == fid[1]
    assert fid[2] != fid[1] and fid[2] == fid[3] == fid[4]
    assert fid[5] != fid[4]
    assert fid[6] not in (fid[0], fid[2], fid[5])


def test_flow_features_carry_a_connections_content_onto_its_empty_packets():
    rows = [_row(time="2021 10:00:00", syn="1"), _row(time="2021 10:00:01", payload=_hex(SQLI_REQUEST)),
            _row(time="2021 10:00:02"), _row(time="2021 10:00:00", sport="53000.0")]
    out = derive_features(pd.DataFrame(rows))
    assert out.shape[1] == 1 + 12 + len(KEYWORD_GROUPS) + 14 + len(KEYWORD_GROUPS)  # 39
    assert out["f_npkts"].tolist() == [3, 3, 3, 1]
    assert out.loc[2, "c_kw_sql"] == 0 and out.loc[2, "f_kw_sql"] >= 1  # the empty ACK inherits its flow's keyword
    assert out.loc[3, "f_kw_sql"] == 0
    assert out.loc[0, "f_syn"] == 1


def test_derive_features_refuses_rows_missing_the_raw_columns():
    with pytest.raises(KeyError, match="tcp.payload"):
        derive_features(pd.DataFrame([_row()]).drop(columns=["tcp.payload"]))


def _capture_like_csv(path, n_per_class=60, seed=0):
    """Minimal CSV with the raw columns the extended path needs; content separates the classes."""
    rng = np.random.default_rng(seed)
    rows = []
    for cls, payload in [("Normal", "hello sensor reading"), ("SQL_injection", SQLI_REQUEST)]:
        for i in range(n_per_class):
            r = _row(time=f"2021 10:{i // 60:02d}:{i % 60:02d}.{rng.integers(0, 999)}",
                     sport=f"{40000 + i}.0", dport="1883.0" if cls == "Normal" else "80.0",
                     payload=_hex(payload) if i % 3 == 0 else "0")
            r.update({"http.request.method": "0", "http.referer": "0", "http.request.version": "0",
                      "dns.qry.name.len": "0", "mqtt.conack.flags": "0", "mqtt.protoname": "0", "mqtt.topic": "0",
                      "tcp.len": float(rng.integers(0, 60)), "Attack_label": int(cls != "Normal"), TARGET_COLUMN: cls})
            rows.append(r)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_load_and_encode_extended_adds_features_and_never_keeps_raw_columns(tmp_path):
    csv = tmp_path / "capture.csv"
    _capture_like_csv(csv)
    X_base, _, _, base_names, _ = load_and_encode(csv)
    X, y, enc, names, benign = load_and_encode(csv, extended_features=True)
    assert "svc_port" in names and any(n.startswith("f_") for n in names) and any(n.startswith("c_") for n in names)
    assert not set(names) & set(DEFAULT_DROP_COLUMNS)
    assert set(base_names) <= set(names) and X.shape[1] == len(names) > X_base.shape[1]
    assert not np.isnan(X).any() and list(enc.classes_) == ["Normal", "SQL_injection"]


def test_load_and_encode_extended_cache_round_trips_and_rebuilds_when_stale(tmp_path):
    csv = tmp_path / "capture.csv"
    cache = tmp_path / "cache.npz"
    _capture_like_csv(csv)
    first = load_and_encode(csv, extended_features=True, cache_path=cache)
    assert cache.exists()
    second = load_and_encode(csv, extended_features=True, cache_path=cache)
    assert np.array_equal(first[0], second[0]) and np.array_equal(first[1], second[1])
    assert first[3] == second[3] and first[4] == second[4]
    assert list(first[2].classes_) == list(second[2].classes_)

    _capture_like_csv(csv, n_per_class=30)  # dataset changed -> the cache must not be reused
    third = load_and_encode(csv, extended_features=True, cache_path=cache)
    assert third[0].shape[0] < first[0].shape[0]


def test_sqrt_class_weighting_upweights_rare_classes():
    from fl_ids.models.boosting import BoostingClassifier
    from fl_ids.utils.config import load_config

    import dataclasses

    cfg = dataclasses.replace(load_config().boosting, class_weighting="sqrt", num_boost_round=5)
    model = BoostingClassifier(cfg, num_classes=3, benign_class=0, seed=0, confidence_threshold=0.7)
    y = np.array([0] * 100 + [1] * 25 + [2] * 4)
    w = model._sample_weights(y)
    assert w[0] == 1.0 and w[100] == pytest.approx(2.0) and w[-1] == pytest.approx(5.0)
    model.train(np.random.default_rng(0).normal(size=(len(y), 4)), y)
    assert model.is_trained

    none_cfg = dataclasses.replace(cfg, class_weighting="none")
    assert BoostingClassifier(none_cfg, 3, 0, 0, 0.7)._sample_weights(y) is None
    with pytest.raises(ValueError):
        BoostingClassifier(dataclasses.replace(cfg, class_weighting="cube"), 3, 0, 0, 0.7)._sample_weights(y)
