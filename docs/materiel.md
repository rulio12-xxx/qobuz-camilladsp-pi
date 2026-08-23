# Réglages matériels — invisibles dans git

## Topping DX5 II
- Line out mode : DAC (niveau fixe, volume numérique contourné)
- PCM filter   : F1
- Volume       : 
- PEQ          : 
- Balance      : 
- Entrée       : 
- Extinction auto : 
- Firmware     : 

## Acoustique — mesures du 26/07/2026
- Distance tweeter → tête : L 2,60 m / R 3,00 m (écart 40 cm)
- Délai appliqué : delay_L = 1,166 ms (canal gauche, le plus proche)
- Balance : balance_L, Peaking 790 Hz, -1,3 dB, Q 0,55
  (compense les 1,24 dB de la loi en carré inverse)
- kick : Peaking 180 Hz, -1,5 dB, Q 0,9, canal DROIT uniquement
  (modes de pièce à 151 et 215 Hz côté droit)

## Décision : pas de FIR de phase
Temps de groupe excédentaire mesuré plat au-dessus de 400 Hz sur L et R.
Les pics étroits sous 300 Hz correspondent à des creux de magnitude
(annulations entre arrivées) : non corrigeables par FIR.
Les PEQ à phase minimale corrigent déjà la phase modale.

## Enceintes
- 3 voies passives, coupures 500 Hz et 8 kHz
- Pentes 18 dB/oct, sauf raccord tweeter à 12 dB/oct
- Pente acoustique réelle : À VÉRIFIER (électrique ≠ acoustique)

## Chaîne numérique
Qobuz FLAC 16/44,1 → proxy (float32) → loopback F32_LE
→ CamillaDSP (float64) → S32_LE → USB → DX5 II
Aucun arrondi entier avant le DAC.

Bluetooth : AAC → BlueALSA S16_LE → loopback → même suite.

## En attente
- Recentrer la place d'écoute (corrigerait délai ET balance)
- Grave en mono sous 80 Hz
- Pont volume Bluetooth vers CamillaDSP
- Webradio
