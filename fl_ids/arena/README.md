# FL-IDS live arena

An interactive demo of the whole system: 5 client networks (3 hosts each) on one core switch, one SDN controller.
Give each host a role (Normal or one of 14 attack types), launch, and watch the cascade judge each host and the
controller install drop rules on the real Open vSwitch switches.

## Start

Inside the VM:

```bash
cd ~/FL-IDS-clean
tools/run_arena.sh          # web UI on http://127.0.0.1:8090 ; Ctrl-C stops everything
```

Open `http://127.0.0.1:8090` and press **Start network** (about 20 s: controller, 6 switches, 15 hosts, models).
The VM has no desktop browser. To view the UI on another machine, forward the port (the page and JSON are the only
traffic that crosses; the captures and packets stay in the VM):

```bash
ssh -L 8090:127.0.0.1:8090 fl-ids-vm      # then browse to http://localhost:8090
```

## What is real

- **Attack hosts** replay the first 12,000 packets of the real Edge-IIoTset capture for that attack (`tcpreplay`
  through the switches; all source IPs rewritten to the host's IP so the per-IP drop rule matches).
- After the host's first **3,000 packets** (the whole capture when shorter: MITM, OS fingerprinting) the features are
  extracted with TShark and the cascade (`models/cascade.py`, bundle `saved_models/full/c10_s42`) scores the window with
  the host's own client's scaler and threshold. A host is an **attacker if at least 25% of its window packets are
  flagged** (`fl_ids/arena/verdict.py`).
- The verdict goes to the existing SDN bridge (`/mitigate`), which installs the drop / rate-limit rule through the
  OpenFlow controller. Drop counts are read from the switches' flow tables.
- **Normal hosts** are scored on real held-out normal rows from the dataset (not sent on the wire): ordinary MQTT
  generated with `mosquitto` in Mininet was flagged as an attack by the model (PAPER_NOTES 8.18).
- The five client networks use clients 1, 2, 3, 7 and 8 of the 10-client bundle, the ones whose anomaly threshold is
  well calibrated on their own held-out normal traffic (`arena_assets/window_benchmark.json`).

## Saved runs

Every finished run is saved to `arena_assets/recordings/`; **Replay a saved run** plays it back in the UI (the UI is a
reducer over the event list), as a backup if the live network misbehaves.

## Rebuild the assets

```bash
venv/bin/python -m fl_ids.arena.make_slices       # capture slices (not in git)
venv/bin/python -m fl_ids.arena.prepare_assets    # held-out normal rows + window benchmark (about 2.5 min)
```
