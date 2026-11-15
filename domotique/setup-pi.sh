#!/bin/bash
# Installation SANS Docker sur le Raspberry : Mosquitto (apt) + service domotique.
# A lancer en root depuis le dossier du projet : sudo ./setup-pi.sh
# Prerequis (deja fait par la preparation) : venv/ et .env dans ce dossier.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-$(stat -c %U "$APP_DIR")}"

[ "$(id -u)" -eq 0 ] || { echo "Lancer avec sudo"; exit 1; }
[ -f "$APP_DIR/.env" ] || { echo "$APP_DIR/.env manquant"; exit 1; }
[ -x "$APP_DIR/venv/bin/python" ] || { echo "venv manquant"; exit 1; }

set -a; . "$APP_DIR/.env"; set +a

apt-get install -y mosquitto mosquitto-clients

cat > /etc/mosquitto/conf.d/domotique.conf <<CONF
listener 1883
allow_anonymous false
password_file /etc/mosquitto/domotique.passwd
CONF
mosquitto_passwd -b -c /etc/mosquitto/domotique.passwd "$MQTT_USER" "$MQTT_PASSWORD"
chown root:mosquitto /etc/mosquitto/domotique.passwd
chmod 640 /etc/mosquitto/domotique.passwd
systemctl enable mosquitto
systemctl restart mosquitto

cat > /etc/systemd/system/domotique.service <<UNIT
[Unit]
Description=Serveur domotique (detection Shelly/Reolink, MQTT, web)
After=network-online.target mosquitto.service
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$APP_DIR/app
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python server.py
Restart=on-failure
RestartSec=5
# Ne doit jamais gener l'audio du Pi
Nice=10
CPUQuota=50%
MemoryMax=300M

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now domotique

sleep 3
systemctl --no-pager --lines=5 status mosquitto domotique || true
echo "Interface : http://$(hostname -I | cut -d' ' -f1):${WEB_PORT:-8100}"
