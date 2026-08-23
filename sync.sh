#!/bin/bash
cd ~/audiohub || exit 1

cp ~/camilladsp/configs/camilladsp-qobuz.yml     camilladsp/
cp ~/camilladsp/configs/camilladsp-bluetooth.yml camilladsp/
cp ~/camilladsp/configs/camilladsp.yml           camilladsp/

cp ~/audio-power/audio-power-monitor.py power/
cp ~/audiohub-selector.py               selector/ 2>/dev/null

for f in bluealsa bt-softvol.service bt-softvol.timer \
         volume-remote.service wifi-nopowersave.service; do
  cp "/etc/systemd/system/$f" systemd/ 2>/dev/null
done
cp /etc/systemd/system/bluealsa.service systemd/ 2>/dev/null

mkdir -p systemd/qobuz-proxy.service.d
cp /etc/systemd/system/qobuz-proxy.service.d/*.conf \
   systemd/qobuz-proxy.service.d/ 2>/dev/null

mkdir -p tools
cp /usr/local/bin/bt-softvol.sh        tools/ 2>/dev/null
cp /usr/local/bin/bt-volume-bridge.py  tools/ 2>/dev/null
cp /usr/local/bin/wifi-watchdog.sh     tools/ 2>/dev/null
cp ~/volume-remote/vol.py              tools/ 2>/dev/null
cp ~/delay-tuner/tuner.py              tools/ 2>/dev/null

git status --short
