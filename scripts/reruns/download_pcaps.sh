#!/bin/bash
set -e
cd ~/FL-IDS-clean; STAGE_DIR=/nonexistent; ALL_PCAPS=1
KAGGLE_DATASET=mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot
KAGGLE_URL=https://www.kaggle.com/api/v1/datasets/download/$KAGGLE_DATASET
# kaggle_get <path inside the dataset> <destination> <expected bytes>
# Kaggle serves single files without a login; large ones arrive zipped.
kaggle_get() {
    local src=$1 dest=$2 size=$3 tmp staged
    if [ -f "$dest" ] && [ "$(stat -c %s "$dest")" = "$size" ]; then
        echo "have   $dest"; return
    fi
    staged="$STAGE_DIR/$(basename "$dest")"
    if [ -f "$staged" ] && [ "$(stat -c %s "$staged")" = "$size" ]; then
        echo "copied $dest (from the host)"; mv "$staged" "$dest"; return
    fi
    echo "fetch  $src"
    tmp=$(mktemp)
    curl -fsSL --retry 3 -o "$tmp" "$KAGGLE_URL/$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$src")"
    if [ "$(head -c 2 "$tmp")" = "PK" ]; then
        unzip -p "$tmp" > "$dest.part"; rm -f "$tmp"
    else
        mv "$tmp" "$dest.part"
    fi
    if [ "$(stat -c %s "$dest.part")" != "$size" ]; then
        echo "size mismatch for $dest: got $(stat -c %s "$dest.part"), want $size" >&2; exit 1
    fi
    mv "$dest.part" "$dest"
}
if [ "${ALL_PCAPS:-0}" = "1" ]; then
    while IFS='|' read -r name size; do
        kaggle_get "Edge-IIoTset dataset/Attack traffic/$name" "data/raw/pcaps/$name" "$size"
    done <<'EOF'
DDoS HTTP Flood Attacks.pcap|28307602
DDoS ICMP Flood Attacks.pcap|212434878
DDoS TCP SYN Flood Attacks.pcap|282613890
DDoS UDP Flood Attacks.pcap|247560012
OS Fingerprinting attack.pcap|114041
Password attacks.pcap|194557494
Port Scanning attack.pcap|1801807
Ransomware attack.pcap|2842688
SQL injection attack.pcap|8173215
Uploading attack.pcap|5488666
Vulnerability scanner attack.pcap|140377652
XSS attacks.pcap|2068899
EOF
fi

echo PCAPS_DONE
