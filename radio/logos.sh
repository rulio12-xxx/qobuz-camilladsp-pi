#!/bin/bash
# Telecharge les logos des stations radio dans ~/radio/logos/
# Usage : ./logos.sh            -> tente toutes les stations
#         ./logos.sh <id> <url> -> ajoute/remplace un logo a la main
#
# Les .svg sont convertis en PNG 128px (necessite librsvg2-bin).

DEST=~/radio/logos
mkdir -p "$DEST"
UA="Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# fetch <id> <url...> : essaie chaque url jusqu'a en trouver une qui marche
fetch() {
  local id=$1; shift
  local u t
  for u in "$@"; do
    if curl -sfL -A "$UA" --max-time 20 "$u" -o "/tmp/logo.$id" 2>/dev/null; then
      t=$(file -b --mime-type "/tmp/logo.$id")
      case "$t" in
        image/svg*)
          if command -v rsvg-convert >/dev/null; then
            rsvg-convert -w 128 -h 128 "/tmp/logo.$id" -o "$DEST/$id.png" \
              && { echo "  $id : OK (svg converti)"; rm -f "/tmp/logo.$id"; return 0; }
          else
            echo "  $id : svg trouve mais rsvg-convert absent (apt install librsvg2-bin)"
          fi
          ;;
        image/*)
          cp "/tmp/logo.$id" "$DEST/$id.png" \
            && { echo "  $id : OK ($t)"; rm -f "/tmp/logo.$id"; return 0; }
          ;;
      esac
    fi
  done
  rm -f "/tmp/logo.$id"
  echo "  $id : ECHEC (aucune source valide)"
  return 1
}

# --- mode manuel : ./logos.sh <id> <url> ---
if [ $# -eq 2 ]; then
  echo "Ajout manuel :"
  fetch "$1" "$2"
  ls -la "$DEST"
  exit
fi

echo "Radio France (Wikimedia Commons) :"
fetch franceinter   "https://commons.wikimedia.org/wiki/Special:FilePath/France_Inter_logo_2021.svg?width=256"
fetch franceculture "https://commons.wikimedia.org/wiki/Special:FilePath/France_Culture_logo_2021.svg?width=256"
fetch fip           "https://commons.wikimedia.org/wiki/Special:FilePath/FIP_logo_2021.svg?width=256"
fetch fipjazz       "https://commons.wikimedia.org/wiki/Special:FilePath/FIP_logo_2021.svg?width=256"
fetch franceinfo    "https://commons.wikimedia.org/wiki/Special:FilePath/Franceinfo.svg?width=256"

echo "Stations privees :"
fetch bfm       "https://www.bfmtv.com/apple-touch-icon.png" \
                "https://www.bfmtv.com/favicon.ico"
fetch nova      "https://upload.wikimedia.org/wikipedia/commons/5/52/Nova_radio.png" \
                "https://www.nova.fr/apple-touch-icon.png"
fetch nostalgie "https://content.sudinfo.be/logotheque/files/dl_logos/dl_logos_otherbrands/logo_nostalgie_color.png" \
                "https://www.nostalgie.fr/apple-touch-icon.png"
fetch tsfjazz   "https://commons.wikimedia.org/wiki/Special:FilePath/Logo%20TSF%20Jazz.png?width=256" \
                "https://commons.wikimedia.org/wiki/Special:FilePath/TSF%20Jazz%20logo.svg?width=256" \
                "https://www.tsfjazz.com/apple-touch-icon.png" \
                "https://www.tsfjazz.com/favicon.ico"

echo
echo "Contenu de $DEST :"
ls -la "$DEST"
echo
echo "Pour ajouter un logo manquant a la main :"
echo "  ~/radio/logos.sh tsfjazz \"https://...\""

