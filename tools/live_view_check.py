"""Render the dashboard's Live Simulation view against the real SDN bridge while Phase B holds, and report what it shows."""
import json
import sys
import time

import requests
from streamlit.testing.v1 import AppTest

BRIDGE = "http://127.0.0.1:8080"
deadline = time.time() + 120
mitigated = False
while time.time() < deadline:
    try:
        hist = requests.get(f"{BRIDGE}/mitigation_history", timeout=3).json()
        if hist:
            mitigated = True
            break
    except requests.RequestException:
        pass
    time.sleep(2)
print("bridge mitigation history non-empty:", mitigated)

app = AppTest.from_file("/home/flids/FL-IDS-clean/fl_ids/dashboard/app.py", default_timeout=60)
app.session_state["view"] = "Live Simulation (Phase B)"
app.session_state["simulation_auto_refresh"] = False  # the 3 s auto-refresh loop never lets AppTest finish
app.run()
errors = [e.value for e in app.error]
exceptions = [e.value for e in app.exception]
print("view header:", [h.value for h in app.header])
print("metrics:", {m.label: m.value for m in app.metric})
print("dataframes:", [(len(d.value), list(d.value.columns)[:6]) for d in app.dataframe])
print("errors:", errors, "exceptions:", exceptions)
ok = mitigated and not errors and not exceptions and len(app.metric) > 0
print("LIVE_VIEW_OK" if ok else "LIVE_VIEW_FAILED")
sys.exit(0 if ok else 1)
