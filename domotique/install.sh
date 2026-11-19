#!/bin/bash
# Installation sur le Raspberry Pi : ./install.sh   (en root)
set -e
D=/opt/domotique
mkdir -p $D && cp -r app docker-compose.yml frigate mosquitto systemd $D/
[ -f $D/.env ] || { cp .env.example $D/.env; echo "-> editer $D/.env"; }
python3 -m venv $D/venv && $D/venv/bin/pip install -q -r $D/app/requirements.txt
cp systemd/domotique.service /etc/systemd/system/ && systemctl daemon-reload
echo "Etapes restantes : mot de passe Mosquitto, montage NAS, docker compose up -d, systemctl enable --now domotique"
