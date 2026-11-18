#!/bin/bash
# Verification a fort volume : ir2 + kick2 a chaque palier, arret si le micro sature.
cd "$(dirname "$0")"
tag="$1"; shift
./reveil.sh
for v in "$@"; do
  curl -s "http://127.0.0.1:8080/vol?t=cdsp&db=$v" >/dev/null; sleep 1
  echo "######## volume $v dB"
  out=$(python3 ir2.py mesure "${tag}_ir_$v")
  echo "$out" | grep -E "pic micro|Clic rel|Bavure|Retard|Traine|ecart G-D"
  pk=$(echo "$out" | sed -n "s/^pic micro \([-+0-9.]*\) dBFS.*/\1/p")
  python3 kick2.py mesure "${tag}_kick_$v" | grep -E "^Pic|Traine|Retard"
  if awk "BEGIN{exit !($pk > -3)}"; then echo "micro proche de la saturation : arret"; break; fi
done
curl -s "http://127.0.0.1:8080/vol?t=cdsp&db=-21" >/dev/null
echo "volume remis a -21 dB"
