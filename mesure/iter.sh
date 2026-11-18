#!/bin/bash
# Une iteration de reglage du kick :
#   ./iter.sh <etiquette> [filtre.param=valeur ...]
# applique les reglages en direct, mesure la reponse (sweeps G et D a -14 dB)
# et le kick (kick2 a -11 dB), sauvegarde tout et affiche le resume.
set -e
cd "$(dirname "$0")"
label="$1"; shift
./reveil.sh
if [ $# -gt 0 ]; then ./regle.py "$@"; fi
mkdir -p iterations/kick
./regle.py delay_L.delay notch_42.gain notch_64.gain "$@" 2>/dev/null | sort -u > "iterations/kick/${label}.txt" || true
python3 campagne.py "it_${label}" -14 | grep -E "pic micro|Restaure" || true
curl -s "http://127.0.0.1:8080/vol?t=cdsp&db=-11" >/dev/null; sleep 1
python3 kick2.py mesure "${label}" | grep -E "Pic|Ecart|Clic rel|Bavure|Retard|Traine|^ +(50|55|60|63|66|70|75|80|90|100) +-"
curl -s "http://127.0.0.1:8080/vol?t=cdsp&db=-21" >/dev/null
python3 lf.py "resultats/$(date +%F)_it_${label}"
