#!/bin/bash
# Inventaire des fichiers de correction sur le Pi, compare au depot git.
# LECTURE SEULE : ne copie rien, ne touche ni a CamillaDSP ni aux YAML actifs.
#
#     cd ~/audiohub && ./correction/inventaire_pi.sh
#
# Ensuite, pour rapatrier dans le depot : ./sync.sh puis git add / commit.
REPO=~/audiohub
CFG=~/camilladsp/configs
FIR=~/camilladsp/fir
cd "$REPO" || exit 1

echo "== git : fichiers modifies ou non suivis dans le depot =="
git status --short
echo

echo "== Configs CamillaDSP : Pi ($CFG) vs depot (camilladsp/) =="
for f in "$CFG"/*.yml "$CFG"/*.yml.avant-tube; do
  [ -e "$f" ] || continue
  b=$(basename "$f")
  if [ ! -e "camilladsp/$b" ]; then echo "ABSENT du depot : $b"
  elif ! cmp -s "$f" "camilladsp/$b"; then echo "DIFFERENT       : $b ($(diff "$f" "camilladsp/$b" | grep -c '^[<>]') lignes)"
  else echo "identique       : $b"; fi
done
for f in camilladsp/*.yml; do
  [ -e "$CFG/$(basename "$f")" ] || echo "Absent du Pi    : $(basename "$f")"
done
echo

echo "== FIR : Pi ($FIR) vs depot (mesure/fir/) =="
for f in "$FIR"/*; do
  [ -e "$f" ] || continue
  b=$(basename "$f")
  if [ ! -e "mesure/fir/$b" ]; then echo "ABSENT du depot : $b"
  elif cmp -s "$f" "mesure/fir/$b"; then echo "identique       : $b"
  else echo "DIFFERENT       : $b"; fi
done
echo

echo "== Sauvegardes *.avant-* sur le Pi (volontairement hors git) =="
ls -l --time-style=+%Y-%m-%d "$CFG"/*.avant-* 2>/dev/null | awk '{print $6, $7}' | sed "s|$CFG/||"
echo

echo "== Etat lampes =="
cat ~/tube/tube.level 2>/dev/null || echo "(pas de ~/tube/tube.level)"
echo

echo "== Scripts de mesure hors depot (anciens emplacements) =="
ls -d ~/bassmeasure.old ~/delay-tuner 2>/dev/null
[ -d ~/bassmeasure.old ] && find ~/bassmeasure.old -maxdepth 1 -name '*.py' -newer mesure/README.md
