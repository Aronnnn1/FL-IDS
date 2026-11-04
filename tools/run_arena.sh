#!/usr/bin/env bash
# Start the FL-IDS live arena (inside the VM). Open http://127.0.0.1:8090 and press "Start network".
# Ctrl-C stops the web server, the controller/bridge and the Mininet network.
set -e
cd "$(dirname "$0")/.."
pkill -f "[f]l_ids.arena.server" 2>/dev/null || true
pkill -f "[f]l_ids.sdn.bridge" 2>/dev/null || true
sudo -n pkill -f "[n]etagent.py" 2>/dev/null || true
sudo -n mn -c >/dev/null 2>&1 || true
exec venv/bin/python -m fl_ids.arena.server
