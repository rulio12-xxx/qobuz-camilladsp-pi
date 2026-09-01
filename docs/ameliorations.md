
## Septembre 2026

### Fiabilisation du démarrage DAC
Le DAC (Topping DX5 II) était référencé en `hw:2,0` (numéro de carte).
Après reboot ou changement USB, le DAC n'était pas toujours énuméré comme
carte 2 au moment du démarrage de CamillaDSP → erreur ALSA `snd_pcm_open
failed` → CamillaDSP crashait en boucle → websocket coupé → le sélecteur
ne pouvait plus basculer les sources (Bluetooth muet).
Correctif : passage au nom stable `hw:CARD=II,DEV=0` dans toutes les
configs. Le nom ne dépend plus du numéro d'énumération. Crashs éliminés.

### Accélération du réveil de la chaîne
Le réveil (détection signal → son) prenait ~4 s, faisant perdre le début
des premiers titres. Optimisations dans audio-power-monitor.py :
- marge d'init DAC après détection USB : 1.0 s → 0.3 s
- délai final après relance CamillaDSP : 2 s → 0.5 s
Résultat : réveil ramené à ~1.5 s. Le reste (énumération USB du DAC) est
matériel, incompressible.

### Ajustement de la correction de pièce
Grave un peu fort à l'écoute : filtres 56, 64 et 70 Hz réduits de +6 à
+5.5 dB (dans les configs .avant-tube, source de la régénération lampes).
