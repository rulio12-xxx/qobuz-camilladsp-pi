#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

install -Dm755 "$HERE/selector/audiohub-selector.py"   "$HOME/audiohub-selector.py"
mkdir -p "$HOME/audio-power"
install -Dm644 "$HERE/power/audio-power-monitor.py"    "$HOME/audio-power/audio-power-monitor.py"
install -Dm644 "$HERE/power/wake.py"                   "$HOME/audio-power/wake.py"

mkdir -p "$HOME/camilladsp/configs"
cp "$HERE/camilladsp/"*.yml "$HOME/camilladsp/configs/"

sudo cp "$HERE/config/aloop.conf" /etc/modprobe.d/aloop.conf
[ -f "$HERE/config/bt-trust.sh" ] && sudo install -Dm755 "$HERE/config/bt-trust.sh" /usr/local/bin/bt-trust.sh

sudo cp "$HERE/systemd/"*.service /etc/systemd/system/
if [ -d "$HERE/systemd/camilladsp.service.d" ]; then
  sudo mkdir -p /etc/systemd/system/camilladsp.service.d
  sudo cp "$HERE/systemd/camilladsp.service.d/"* /etc/systemd/system/camilladsp.service.d/
fi
sudo systemctl daemon-reload
sudo systemctl enable camilladsp audio-power bt-open audiohub-selector

echo "OK. Creer ~/qobuz-proxy/config.yaml puis : sudo reboot"
