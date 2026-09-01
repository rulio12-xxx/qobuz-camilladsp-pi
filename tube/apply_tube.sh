#!/bin/bash
# Applique l'etage lampes (niveau 0-3) aux 2 configs source, avec backup.
# Usage: ./apply_tube.sh <niveau>
LEVEL=${1:-0}
CFG=~/camilladsp/configs
SCRIPT=~/tube/make_tube_config.py

for src in qobuz bluetooth; do
    f="$CFG/camilladsp-$src.yml"
    # backup une seule fois (garde l'original propre)
    [ -f "$f.avant-tube" ] || cp "$f" "$f.avant-tube"
    # generer depuis l'original propre, vers le fichier actif
    python3 "$SCRIPT" "$f.avant-tube" "/tmp/$src-tube.yml" "$LEVEL"
    if camilladsp --check "/tmp/$src-tube.yml" 2>&1 | grep -q "Config is valid"; then
        cp "/tmp/$src-tube.yml" "$f"
        echo "OK $src : niveau $LEVEL applique"
    else
        echo "ERREUR $src : config invalide, non appliquee"
        camilladsp --check "/tmp/$src-tube.yml" 2>&1 | tail -3
    fi
done
echo "$LEVEL" > /home/rulio12/tube/tube.level
