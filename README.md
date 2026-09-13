# AudioHub DSP

Preampli numerique multi-sources sur Raspberry Pi 5 + CamillaDSP.
Selection automatique de source, correction de piece, emulation lampes,
loudness automatique, extinction/reveil du DAC, pilotage web.

DAC : Topping DX5 II (USB, nom stable `hw:CARD=II,DEV=0`).

## Architecture

Chaque source ecrit dans son propre tuyau ALSA (snd-aloop). Le selecteur
detecte la source active et demande a CamillaDSP de charger la config
correspondante (websocket port 1234).

| Source    | Entree                          | Capture CamillaDSP | Config              |
|-----------|---------------------------------|--------------------|---------------------|
| Fichiers  | MPD -> hw:10,0,1 (sous-flux 1)  | hw:10,1,1          | camilladsp-fichiers |
| Qobuz     | qobuz-proxy -> hw:10,0          | hw:10,1            | camilladsp-qobuz    |
| Bluetooth | bluealsa-aplay -> hw:11,0 (AAC) | hw:11,1            | camilladsp-bluetooth|
| S/PDIF    | WM8805 -> I2S (en cours)        | hw:CARD=spdifin    | a venir             |

MPD sert les fichiers locaux (~/musique) **et** les webradios : les deux
passent par le meme tuyau, donc par la source "Fichiers".

## Priorite stricte

    Fichiers > Qobuz > Bluetooth

Anti-rebond : 2 s actif / 5 s silence. Lancer une radio ou un album prend
la main sur Qobuz ; arreter MPD (`mpc stop`, bouton Arreter, ou Stop dans
myMPD) rend la main.

## Gestion de l'alimentation

`audio-power/audio-power-monitor.py` (un seul service, un seul etat) :

- **Reveil anticipe** : un thread suit les logs de qobuz-proxy ; des
  l'evenement `Renderer set active: True` (connexion de l'app), le DAC est
  alimente et CamillaDSP relance, sans attendre le son.
- **Reveil sur signal** : filet de securite pour les autres sources
  (detection de niveau sur les tuyaux, voir `WAKE_DEVICES`).
- **Delai de grace** (`WAKE_GRACE`, 60 s) : pas d'extinction juste apres un
  reveil, meme si le son tarde.
- **Extinction** : apres `IDLE_TIMEOUT` (600 s) de pause, stop CamillaDSP,
  coupure du 5 V USB (uhubctl hub 3 port 2), redemarrage de qobuz-proxy.

## Emulation lampes

Processor `Compressor` avec `soft_clip` (distorsion harmonique douce),
insere en fin de pipeline avant le limiter global.

    ~/tube/apply_tube.sh <0-3>     # 0 = off, 3 = fort

Le script regenere chaque `camilladsp-<source>.yml` depuis son
`.avant-tube` (reference sans lampes), valide par `camilladsp --check`
avant d'ecrire, et memorise le niveau dans `~/tube/tube.level`.
Dans le hub : boutons Lampes Off / Lampes On (niveau 3).

## Loudness automatique

`loudness/loudness.py` (service `loudness`) compense grave et aigu selon
le niveau d'ecoute, facon Fletcher-Munson.

- Niveau global = volume USB du DAC + volume principal CamillaDSP.
  La molette physique du DAC n'est pas lisible et reste hors calcul.
- Reference `REF_DB = -17.5` : compensation nulle a ce niveau.
- En dessous : +1 dB de grave par 4 dB manquants (plafond +8), aigu a
  la moitie.
- Les gains sont appliques par `set_value` sur les filtres `loud_bass`
  (Lowshelf 120 Hz) et `loud_treble` (Highshelf 8 kHz) : modification a
  chaud, sans rechargement ni coupure.
- Active par la presence de `~/loudness/enabled` (boutons du hub).

## Hub web (port 8080)

`hub/audio-hub.py`. Installable en PWA plein ecran (manifeste + icone SVG).

| Onglet     | Contenu                                                      |
|------------|--------------------------------------------------------------|
| Statuts    | pastilles DAC/flux/BT, services, curseurs volume, lampes, loudness |
| Radios     | 9 stations en grille avec logos (~/radio/logos)              |
| Musique    | myMPD en iframe (port 8082)                                  |
| CamillaGUI | iframe port 5005                                             |
| Qobuz      | iframe port 8689                                             |

Curseurs : **DAC** (amixer, controle `DX5 II`, -60 a 0 dB) et **Camilla**
(websocket, `main_volume`). Qobuz est affiche en lecture seule : le proxy
n'expose aucune route de volume.

## Composants

- `selector/audiohub-selector.py` : selection de source
  (le fichier de reference est `~/audiohub-selector.py`)
- `power/audio-power-monitor.py` : alimentation DAC + reveil anticipe
- `loudness/loudness.py` : loudness automatique
- `tube/` : generation des configs avec etage lampes
- `camilladsp/*.yml` : configs actives ; `*.avant-tube` : references
- `radio/` : mpd.conf, logos.sh, logos des stations
- `hub/audio-hub.py` : interface web
- `systemd/` : unites

## Points de vigilance

- **Noms de devices stables uniquement.** L'ajout de la carte SPDIF a
  decale le DAC de la carte 2 a la carte 3 : utiliser `hw:CARD=II,DEV=0`
  et `amixer -c II`, jamais de numero.
- **Le selecteur depend de CamillaDSP** (`PartOf=camilladsp.service`) :
  apres un restart de CamillaDSP, il doit recharger la config de la
  source courante, sinon CamillaDSP repart sur `camilladsp.yml` et ecoute
  le mauvais tuyau (silence).
- **Ajouter une source** = creer sa config, l'ajouter au selecteur
  (`CONFIG` + classe Source), a `WAKE_DEVICES` du moniteur, et a la
  liste de `apply_tube.sh`.
- **Le volume USB du DAC n'apparait pas sur son ecran** : molette et
  volume USB sont deux etages independants qui se cumulent.

## Bugs amont signales (qobuz-proxy)

- Skip bloque sur desync de file : **corrige**
- Titres indisponibles : **corrige**
- Skip qui re-telecharge la piste deja prechargee : **corrige**
- `fixed_volume` ignore sur le backend local : ouvert
- Pas de route volume sur l'API HTTP locale : ouvert

## A faire

- [ ] Carte SPDIF WM8805 : aucune horloge ne parvient au Pi (overlay et
      brochage valides cote Pi, diagnostic materiel a faire)
- [ ] Logo Nostalgie (site protege, 403)
- [ ] Volume unifie (bouton du telephone -> volume DAC)
- [ ] Ordre lampes / correction de piece a comparer a l'oreille
# AudioHub DSP V1

Preampli multi-sources sur Raspberry Pi 5 + CamillaDSP.
Selection automatique de source en priorite stricte, correction de piece,
extinction/reveil automatique du DAC.

## Architecture

Chaque source a son propre loopback ALSA (snd-aloop, cartes 10 et 11).
La bascule se fait cote CamillaDSP (reload via websocket port 1234).

| Source     | Entree                          | Capture |
|------------|---------------------------------|---------|
| Qobuz      | qobuz-proxy -> hw:10,0          | hw:10,1 |
| Bluetooth  | bluealsa-aplay -> hw:11,0 (AAC) | hw:11,1 |
| S/PDIF x3  | WM8805 -> I2S (a venir)         | a venir |

## Priorite stricte

    Qobuz > Optique > Coax1 > Coax2 (phono) > Bluetooth

Anti-rebond : 2 s actif / 5 s silence. Phono detecte au niveau audio.

## Bluetooth

BlueALSA compile avec AAC, profil a2dp-sink. Appairage ouvert (bt-open.service).
Multi-appareils "chacun son tour" : bluealsa-aplay sans MAC.

## Composants

- selector/audiohub-selector.py : selection de source
- power/audio-power-monitor.py + wake.py : gestion DAC
- camilladsp/*.yml : configs par source
- systemd/*.service : unites
- config/aloop.conf : 2 loopbacks

## Installation

    ./install.sh

Puis creer ~/qobuz-proxy/config.yaml (voir config/qobuz-config.example.yaml).

## A faire

- [ ] Egalisation niveau Bluetooth / Qobuz
- [ ] Integration WM8805 (I2C selection + frequence)
- [ ] Ecran ST7789 + bouton + LED
- [ ] Reconnexion auto websocket dans le selecteur
