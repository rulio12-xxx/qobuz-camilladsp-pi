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

## Notes

- `hwaccel_args` de Frigate est regle pour le Pi 5 ; a adapter sur mini-PC (`preset-vaapi`).
- Detection CPU suffisante pour 3 cameras en sous-flux ; ajouter un Coral/Hailo si besoin.
- Scan Bluetooth : le service doit tourner avec acces a BlueZ (`BLE_SCAN=0` pour le couper).
- Aucun secret dans le depot : `.env` et `mosquitto/passwd` sont ignores par git.
- Reste a faire : pilotage chauffe-eau/voiture, mesure reseau, monitoring, solaire/batterie.
