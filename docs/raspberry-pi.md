# Raspberry Pi « CamillaDSP » : vue d'ensemble

Document de reference : ce qui tourne sur le Pi, ou c'est, et comment ca s'articule.
Etat releve le 2026-11-15 (lecture seule, aucun secret dans ce fichier).

## Machine

| | |
|---|---|
| Modele | Raspberry Pi 5 Model B, 4 Go de RAM |
| Systeme | Debian 13 (trixie), noyau 6.18 `rpt-rpi-2712`, Python 3.13 |
| Nom d'hote | `CamillaDSP` |
| Utilisateur | `rulio12` (SSH par cle ; `sudo` demande un mot de passe) |
| Reseau | **Wi-Fi uniquement** (`wlan0`, 192.168.1.81/24, pas d'Ethernet) |
| Stockage | carte SD 59 Go (environ 16 % utilises) |

Contrainte a retenir : le Pi est **d'abord un preampli audio**. Tout ajout doit rester leger
(pas de Docker/NVR ici, pas de scan Bluetooth) pour ne jamais perturber le son.

## Les trois projets installes

| Projet | Role | Dossier sur le Pi | Source |
|---|---|---|---|
| **AudioHub DSP** | Preampli numerique multi-sources (Fichiers, Qobuz, Bluetooth, S/PDIF a venir) avec CamillaDSP, correction de piece, lampes, loudness, extinction du DAC | `~/hub`, `~/camilladsp`, `~/loudness`, `~/tube`, `~/radio`, `~/audio-power`, `~/qobuz-proxy`... | ce depot (voir `README.md`) |
| **Domotique** | Detection Shelly/Reolink, broker MQTT, tarifs HP/HC, interface web | `~/domotique` | ce depot, dossier `domotique/` |
| **Vigie patrimoine** | Surveillance de placements (seuils, signaux, notifications), robot sur cron | `~/vigie` | depot GitHub prive `vigie-patrimoine` (hors de ce depot) |

## Services et ports

| Port | Service systemd | Role |
|---|---|---|
| 22 | `ssh` | acces distant |
| 5005 | `camillagui` | interface CamillaDSP |
| 6600 | `mpd` | lecteur de fichiers et webradios |
| 8080 | `audio-hub` | **hub web audio** (statuts, radios, volumes, iframes) |
| 8082 | `mympd` | interface MPD |
| 8091 | `volume-widget` | curseur de volume (`~/volume-widget`) |
| 8689 / 8690 | `qobuz-proxy` | lecteur Qobuz (UPnP/Connect) |
| 111 | `rpcbind` | systeme |
| **1883** | `mosquitto` | broker MQTT (authentifie) |
| **8100** | `domotique` | interface domotique (8080 est pris par le hub) |

Autres unites audio : `camilladsp`, `audiohub-selector`, `audio-power`, `loudness`, `wm8805`,
`bluealsa`, `bt-softvol` (+ timer), `bt-open`, `qobuz-wake`, `selector-watchdog` (+ timer).
`camilladsp` est parfois **inactif volontairement** : le moniteur d'alimentation l'arrete et coupe
le DAC apres 10 minutes sans son, puis le relance au reveil.

## Taches planifiees (cron, utilisateur `rulio12`)

| Heure (lun-ven) | Commande |
|---|---|
| 07:40 | `vigie-patrimoine/pi/robot.sh matin` |
| 08:17 a 17:17, chaque heure | `vigie-patrimoine/pi/robot.sh robot` |
| 17:50 et 22:17 | `vigie-patrimoine/pi/robot.sh robot` |

Journaux : `~/vigie/robot.log` et `~/vigie/relance.log`. Un `relance.sh` declenche un
workflow GitHub de secours avec un jeton lu dans `~/vigie/token` (**secret : ne jamais le copier,
l'afficher ni le versionner**).

## Dossiers du repertoire personnel

Audio : `audiohub`, `audio-power`, `bassmeasure`, `bluez-alsa`, `camilladsp`, `camillagui`,
`dashboard` (verif. des mises a jour Qobuz), `delay-tuner`, `hub`, `loudness`, `musique`/`Music`,
`qobuz-proxy` (+ `qobuz-proxy-venv`), `radio`, `spdifin`, `tube`, `volume-widget`.
Non documentes ici (a completer) : `kickbody`, `notch`, `rfix`.
Autres : `domotique`, `vigie`, dossiers de bureau standard (`Desktop`, `Documents`...).

## Domotique : etat et decisions

- **Sans Docker** : Mosquitto en paquet `apt`, serveur Python dans `~/domotique/venv`, service
  `domotique` limite a 50 % d'un coeur, 300 Mo, priorite basse (`Nice=10`).
- **Pas de Frigate sur le Pi** (Wi-Fi + audio). Pour les 3 cameras Reolink PoE, l'option
  retenue est l'enregistrement sur leur carte microSD (a verifier : presence de la carte) ;
  Frigate tournera plus tard sur une machine en Ethernet, avec ce broker.
- **Scan Bluetooth desactive** (`BLE_SCAN=0`) : il partage la radio avec l'audio A2DP.
- **Installe le 2026-11-15** via `sudo ~/domotique/setup-pi.sh` : Mosquitto 2.0 (acces par mot de passe
  obligatoire, utilisateur `domotique`) et service `domotique` actifs ; l'audio n'est pas affecte.
- Topics MQTT : `domotique/status`, `domotique/devices/<id>` (retenus), `domotique/tariff`
  (apres creation de `tariff.json`).
- Detection : 1 Shelly 1 Gen3 trouve (192.168.1.43, sans mot de passe) ; aucune Reolink vue sur le
  sous-reseau 192.168.1.0/24 (autre reseau ou interface web desactivee ?).
- Secrets : `~/domotique/.env` (droits 600) ; jamais dans le depot.
- Reste a faire : tarifs reels (`tariff.json`), pilotage chauffe-eau et voiture, mesure reseau,
  couts, solaire/batterie.

## Regles de cohabitation

1. Ne pas utiliser un port deja liste ci-dessus ; reserver ici tout nouveau port.
2. Tout nouveau service lourd passe par une limite systemd (`CPUQuota`, `MemoryMax`, `Nice`).
3. Pas de scan Bluetooth ni de charge continue pendant l'ecoute.
4. Noms de devices audio stables uniquement (`hw:CARD=II,DEV=0`), jamais de numeros de carte.
5. Aucun secret dans le depot : jetons, mots de passe et `.env` restent sur le Pi.

## Acces et depannage rapides

    ssh rulio12@192.168.1.81
    systemctl status audio-hub camillagui mpd qobuz-proxy domotique mosquitto
    journalctl -u domotique -n 50 --no-pager
    ss -tlnp                       # ports en ecoute
    crontab -l                     # taches planifiees

Hub audio : `http://192.168.1.81:8080` · Domotique : `http://192.168.1.81:8100`.
