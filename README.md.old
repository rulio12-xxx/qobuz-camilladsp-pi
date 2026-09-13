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
