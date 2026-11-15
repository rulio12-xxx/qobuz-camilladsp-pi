# Domotique

Serveur maison sur Raspberry Pi : detection des appareils (Shelly, Reolink,
Bluetooth), broker MQTT, NVR Frigate (3 cameras Reolink PoE, enregistrement
sur disque reseau) et interface web simplifiee.

    Cameras PoE --RTSP--> Frigate --MQTT--> Mosquitto <--> serveur domotique (web :8100)
    Shelly ------------MQTT-----------------^                 |-- scan reseau (HTTP/mDNS/ONVIF)
                                                              '-- scan Bluetooth (BLE)

## Contenu

| Element | Role |
|---|---|
| `docker-compose.yml` | Mosquitto (1883, WebSocket 9001) + Frigate (5000) |
| `frigate/config.yml` | 3 cameras Reolink : flux principal enregistre, sous-flux detecte |
| `app/discovery.py` | Detection Shelly (`/shelly`, mDNS), Reolink (`/api.cgi`, ONVIF), BLE |
| `app/tariff.py` | Tarif HP/HC : periode courante, repartition de l'energie, couts, economies |
| `app/server.py` | API + publication MQTT `domotique/devices/<id>` (retenu) + page web |

## Installation

1. `cp .env.example .env` puis adapter (IP des cameras, mots de passe).
2. Utilisateur MQTT :
   `docker run --rm -v $PWD/mosquitto:/m eclipse-mosquitto:2 mosquitto_passwd -b -c /m/passwd domotique <mot_de_passe>`
3. Disque reseau (NFS) dans `/etc/fstab`, puis `NAS_RECORDINGS=/mnt/nas/frigate` dans `.env` :
   `nas.local:/volume1/frigate /mnt/nas/frigate nfs defaults,_netdev,x-systemd.automount,nofail 0 0`
4. Cameras Reolink : creer un utilisateur dedie dans chaque camera, activer RTSP/ONVIF
   (Reglages > Reseau > Avance > Controle du serveur), IP fixes (reservation DHCP).
5. `docker compose up -d` puis `sudo ./install.sh && sudo systemctl enable --now domotique`.
6. Interface : `http://<ip-du-pi>:8100` (bouton Scanner pour relancer la detection).

## Installation sans Docker (Pi audio, en Wi-Fi)

Sur le Pi qui fait deja l'audio, on n'installe ni Docker ni Frigate : seulement Mosquitto
(paquet apt) et le serveur domotique, sous un service systemd limite a 50 % d'un coeur et
300 Mo (`Nice=10`). Le NVR (Frigate) tournera sur une machine en Ethernet et utilisera ce broker.

1. Copier `app/`, `setup-pi.sh`, `.env.example` dans `~/domotique` sur le Pi, puis
   `python3 -m venv venv && venv/bin/pip install -r app/requirements.txt`.
2. Creer `.env` depuis `.env.example` (mot de passe MQTT genere, `BLE_SCAN=0`).
3. `sudo ~/domotique/setup-pi.sh` : installe Mosquitto, cree l'utilisateur MQTT et le service `domotique`.

Le scan Bluetooth reste desactive (`BLE_SCAN=0`) : il partage la radio avec l'audio A2DP.

## Shelly

Detectes automatiquement. Pour qu'ils parlent au broker : interface du Shelly >
Settings > MQTT, serveur `<ip-du-pi>:1883`, utilisateur/mot de passe MQTT.

## Tarifs HP/HC

`cp tariff.example.json tariff.json` puis renseigner **vos** prix (TTC, depuis la facture) et vos
plages d'heures creuses. Aucun prix n'est fourni par defaut.

- MQTT : `domotique/tariff` (retenu) = `{"period": "HC", "eur_kwh": ..., "next_switch": <epoch>}`,
  republie a chaque bascule. Les regles de pilotage (chauffe-eau, voiture) s'abonneront a ce topic.
- API : `GET /api/tariff` ; `POST /api/tariff/report` avec `{"intervals": [[debut, fin, kWh], ...]}`
  (timestamps epoch) renvoie kWh HP/HC, cout, et economies : `savings_vs_all_hp_eur` (gain du
  decalage en heures creuses) et `savings_vs_base_eur` si `base_eur_kwh` est renseigne.
- Un intervalle a cheval sur une bascule est reparti au prorata du temps ; tests : `python3 -m unittest test_tariff` dans `app/`.

## Pilotage des Shelly

Section « Pilotage » de l'interface : **Allumer**, **Eteindre**, **Auto HC** (relais allume pendant les
heures creuses, eteint en heures pleines).

- **Mode manuel par defaut** : rien n'agit seul tant qu'on n'a pas choisi Auto. Un clic Allumer/Eteindre
  repasse en manuel.
- **Auto refuse sans `tariff.json`** (heures creuses inconnues). `tariff.json` est relu a chaud.
- **Prudence** : Shelly injoignable ou tarif absent = aucune commande ; l'etat est relu toutes les 30 s.
- **Journal** : `~/domotique/state/actions.jsonl` (commandes, changements de mode, pertes de contact),
  consultable via `GET /api/control/log`. Mode memorise dans `state/control.json`.
- **MQTT** : `domotique/control/<id>/state` (mode, joignable, etat du relais).
- API : `GET /api/control`, `POST /api/control/<id>/mode` `{"mode":"auto"|"manual"}`,
  `POST /api/control/<id>/switch` `{"on":true|false}`.
- Pas d'authentification sur l'API : tout appareil du Wi-Fi peut commander le relais.

## Notes

- `hwaccel_args` de Frigate est regle pour le Pi 5 ; a adapter sur mini-PC (`preset-vaapi`).
- Detection CPU suffisante pour 3 cameras en sous-flux ; ajouter un Coral/Hailo si besoin.
- Scan Bluetooth : le service doit tourner avec acces a BlueZ (`BLE_SCAN=0` pour le couper).
- Aucun secret dans le depot : `.env` et `mosquitto/passwd` sont ignores par git.
- Reste a faire : pilotage chauffe-eau/voiture, mesure reseau, monitoring, solaire/batterie.
