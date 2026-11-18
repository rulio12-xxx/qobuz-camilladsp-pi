# Mesure et calibration acoustique

Outils de mesure de la chaine (micro de mesure sur le **Scarlett 2i2**, entree 1).
Tous les scripts se lancent depuis ce repertoire, sur le Pi :

    cd ~/audiohub/mesure

`~/bassmeasure` est un lien vers ce repertoire (ancien emplacement, garde pour
compatibilite). L'ancienne copie hors depot est dans `~/bassmeasure.old`.

## Materiel

- Capture : `hw:USB,0` (nom ALSA du Scarlett, stable meme si le numero de carte
  change en changeant de port USB ; avant le 18/11/2026 les scripts utilisaient
  `hw:3,0`, devenu l'entree S/PDIF).
- Micro sur l'**entree 1** du Scarlett (`MIC_CHANNEL = 0`). Si le micro passe sur
  l'entree 2, mettre `MIC_CHANNEL = 1` dans les scripts concernes.
- Verifier qu'aucun coup ne sature (LED de gain du Scarlett, et `Pic du coup
  analyse` dans `measure_kick.py`, a garder sous ~ -3 dBFS).

## Test du kick de batterie (decroissance du grave)

1. `gen_kick.py` : genere `~/musique/kick_test.wav` (kick de synthese, note qui
   descend de 150 a 55 Hz + clic de 4 ms ; 7,5 s d'amorce puis 6 coups espaces
   de 1 s). A relancer seulement si le son de test doit changer.
2. `play_record_kick.py` : joue le son une fois a blanc (reveil de la chaine),
   puis le rejoue par MPD en enregistrant le micro dans `/tmp/kick_rec.wav`.
3. `measure_kick.py` : recale le dernier coup sur le son d'origine par
   correlation, filtre les deux en 40-120 Hz et mesure le temps de chute de
   -20 dB. Ecrit le detail dans `/tmp/kick_compare.json`.

Diagnostics : `diag_kick_rec.py`, `diag_kick_rec2.py` (niveau de chaque coup),
`check_kick_file.py` (controle du fichier source).

Note : la valeur "Mesure" depend aussi de la courbe de reponse (si les 50-60 Hz
sont plus bas que les 80-100 Hz, l'enveloppe chute plus vite). Elle sert a
comparer deux reglages a position de micro identique, pas a comparer des
mesures faites avec le micro a des endroits differents.

## Iterations de reglage

Chaque etape de reglage est un petit JSON `{"nom_du_filtre": gain_dB, ...}`
applique en direct a CamillaDSP, puis remesure :

    python3 apply_iter.py iterations/2026-10-09_equilibrage_LR/iter5.json

Attention : un changement de source (rechargement de la config) efface ces
reglages live ; reporter les valeurs retenues dans les YAML de `camilladsp/`.

- `iterations/2026-10-09_equilibrage_LR/` : 17 iterations de l'equilibrage L/R
  (`measure_lr_bass.py` 20-1000 Hz, `check_treble_centered.py` 500 Hz-16 kHz),
  puis `ease_treble_rolloff.json` et `push_treble_air.json` (aigu 8-14 kHz).

## Autres outils

- `measure.py`, `sweep_dsp.py`, `gen_sweep.py`, `gen_warm_sweep.py` : sweep +
  deconvolution (reponse en frequence).
- `measure_lr_bass.py`, `check_treble_centered.py` : ecart L/R.
- `find_resonance.py` : sweep fin 20-160 Hz (resonances 42/64 Hz).
- `measure_thd.py`, `gen_tones.py` : THD+N par grille de tons.
- `measure_matrix.py`, `analyze_matrix.py` : matrice niveau x voie.
- `iterate_delay.py`, `delay_centered.py`, `reanalyze_delay.py` : delai L/R.
- `selftest*.py` : auto-tests synthetiques des methodes.

## Resultats

`resultats/` : resultats dates. `history/` : courbes avant/apres de septembre.
