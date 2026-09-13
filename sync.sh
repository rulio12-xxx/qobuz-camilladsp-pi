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

# --- ajouts recents ---
mkdir -p hub tube radio
cp ~/hub/audio-hub.py                             hub/ 2>/dev/null
cp ~/tube/make_tube_config.py                     tube/ 2>/dev/null
cp ~/tube/apply_tube.sh                           tube/ 2>/dev/null
cp ~/camilladsp/configs/*.yml.avant-tube          camilladsp/ 2>/dev/null
cp ~/radio/mpd.conf                               radio/ 2>/dev/null
cp /etc/systemd/system/audio-hub.service          systemd/ 2>/dev/null
cp /etc/systemd/system/audiohub-selector.service  systemd/ 2>/dev/null
cp /etc/systemd/system/camilladsp.service         systemd/ 2>/dev/null
cp /etc/systemd/system/camillagui.service         systemd/ 2>/dev/null
cp /etc/systemd/system/audio-power.service        systemd/ 2>/dev/null
cp /etc/systemd/system/mpd.service                systemd/ 2>/dev/null
cp /etc/mpd.conf                                  radio/mpd-system.conf 2>/dev/null

git status --short
cp ~/spdifin.dts                                  systemd/ 2>/dev/null
cp /etc/systemd/system/mympd.service              systemd/ 2>/dev/null
cp /etc/systemd/system/qobuz-wake.service         systemd/ 2>/dev/null
cp ~/qobuz-proxy/config.yaml                      config/qobuz-proxy-config.yaml 2>/dev/null
