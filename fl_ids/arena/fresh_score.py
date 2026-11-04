"""Score the fresh captures (made in isolated namespaces) with the real cascade, same host rule as the arena.

Run in the VM:  venv/bin/python -m fl_ids.arena.fresh_score
Writes arena_assets/fresh_results.json. Nothing is tuned: same bundle, same 3,000-packet window, same 25% host rule.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fl_ids.arena.verdict import WINDOW_PACKETS, SHARE_THRESHOLD, window_verdict
from fl_ids.orchestration.artifacts import load_phase_a_artifacts
from fl_ids.sdn.feature_extraction import extract_features_for_inference
from fl_ids.utils.config import load_config

cfg = load_config(ROOT / "configs" / "full" / "c10_s42.yaml")
art = load_phase_a_artifacts(ROOT / "saved_models" / "full" / "c10_s42", cfg.boosting)
CLIENTS = [1, 2, 3, 7, 8]  # the bundle clients the arena networks use
FRESH = ROOT / "arena_assets" / "fresh"
res = {}
for p in sorted(FRESH.glob("*.pcap")):
    truth = p.stem
    try:
        X = extract_features_for_inference(p, art.feature_names)[:WINDOW_PACKETS]
    except Exception as e:  # noqa: BLE001
        print(f"{truth}: extraction failed: {e}")
        continue
    rows = []
    for c in CLIENTS:
        v = window_verdict(art, c, X, SHARE_THRESHOLD)
        rows.append({"client": c, "label": v.label, "is_attack": bool(v.is_attack), "confidence": round(float(v.confidence), 3),
                     "share": round(float(v.share_flagged), 3), "stage": v.stage})
    res[truth] = {"packets": int(len(X)), "verdicts": rows}
    det = sum(r["is_attack"] for r in rows)
    typed = sum(r["label"] == truth for r in rows)
    print(f"{truth:22s} packets={len(X):5d} detected_as_attack={det}/5 named_correctly={typed}/5 "
          f"labels={sorted(set(r['label'] for r in rows))} share={[r['share'] for r in rows]}", flush=True)
(ROOT / "arena_assets" / "fresh_results.json").write_text(json.dumps(res, indent=1))
