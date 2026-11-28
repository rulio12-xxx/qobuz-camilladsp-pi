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

## Event bass-reflex en champ proche (27/11/2026)

Mesure de l'event et du woofer micro colle (1 cm), sans REW. Protocole complet :
document "Protocole de mesure de l'event bass-reflex" (claude.ai).

    python3 event.py gen                               # une fois : ~/musique/event_G.wav, event_D.wav
    ./reveil.sh
    python3 event.py mesure 2026-11-28 "bruit G"       # bruit de fond (aucun son joue)
    python3 event.py mesure 2026-11-28 "woofer G"      # micro a 1 cm du cache-noyau
    python3 event.py mesure 2026-11-28 "woofer G2"     # repetition, micro recule de quelques mm
    python3 event.py mesure 2026-11-28 "event G"       # micro dans le plan de sortie de l'event
    python3 event.py mesure 2026-11-28 "event G2"      # repetition, micro decale de 1 cm
    ... idem avec D ...
    python3 event.py analyse 2026-11-28 --d-membrane 330 --d-event 100 --l-event 250 --vb 180
    python3 event.py selftest                          # chaine complete sur une enceinte simulee

- Sweep log 10 Hz-20 kHz de 16 s sur un seul canal, joue par MPD (comme ir2.py).
  Refuse de mesurer si le volume CamillaDSP depasse -40 dB (`--volume-max` pour changer).
- Ne pas toucher au gain du Scarlett ni au volume entre woofer et event d'un meme cote.
- Pas de reference de temps entre deux mesures (latence MPD variable) : la somme
  woofer + event utilise la phase minimale reconstruite (valable dans le grave en
  champ proche). L'event est mis a l'echelle par le rapport des diametres (Keele).
- Sorties dans `resultats/event/<session>/` : une reponse par mesure (.npz + .json),
  et `analyse/` (resume.md, resultats.json, courbes PNG si matplotlib est installe).
- `event_analyse.py` lit aussi les fichiers REW (.mdat ou export texte).
- Event a bords arrondis : `--l-event` = longueur TOTALE bord a bord, `--rayon-bords`
  (mm) et `--bords-arrondis 1|2`. La masse d'air est integree le long du profil.
- Rembourrage : `--remplissage aucun|parois|partiel|plein` (volume apparent +0/5/10/15 %)
  et `--dist-mousse` (mm entre le rembourrage et l'entree interieure de l'event ;
  alerte sous un diametre).

Fort niveau (en journee) : paliers croissants sur l'event ou le woofer, micro en place.

    python3 event.py niveaux 2026-11-28 "event G" -40 -34 -28 -22 -16 -10

- Sweep 20 Hz-20 kHz (`event_G_fort.wav`, cree par `gen`). Confirmation `oui` avant
  de lancer, plafond -10 dB par defaut (`--volume-max`), volume remis a la fin meme sur Ctrl-C.
- A chaque palier : compression du grave par rapport au premier palier, H2 et H3
  (methode de Farina), pic du micro. Arret au premier signe de limite :
  compression > 3 dB, H3 > 10 % (20-150 Hz) ou micro > -3 dBFS.
- Le micro colle a l'event sature vite : baisser le gain du Scarlett avant (et
  le garder pour tous les paliers).
- Resultat : `resultats/event/<session>/<nom>_niveaux.json` + une reponse par palier.

Notes /10 (`event_notes.py`, seuils dans `event_notes.json`, modifiables) : chaque
caracteristique est notee contre deux references, audiophile (cible 105 dB SPL de
crete a la place d'ecoute) et pro (115 dB SPL). Criteres : accord identique G/D,
extension grave (-3 dB), bosse de la somme, retard de groupe (en cycles), resonance
de tuyau par rapport au woofer, forme du grave G/D, compression, H3 et H2 au niveau
cible, niveau max propre (compression < 1 dB et H3 < 3 %). Note globale ponderee.

    python3 event.py analyse 2026-11-28 --d-membrane 330 --d-event 100 --spl -30:85

- `--spl V:SPL` : a V dB CamillaDSP, le sonometre lit SPL dB a la place d'ecoute
  avec le bruit rose de `python3 event.py rose G` (-20 dBFS RMS, 20 Hz-20 kHz, en
  boucle, Entree pour arreter ; ponderation C, une appli de telephone suffit pour
  commencer). Comme la norme cinema : 85 dB de bruit rose = 105 dB de crete.
  La crete du sweep des paliers est 16,9 dB au-dessus du bruit rose.

Calibreur de micro (1 kHz, 94 ou 114 dB) : niveaux absolus en dB SPL.

    python3 event.py calib 2026-11-28 --niveau 94    # gain normal, avant les mesures
    python3 event.py rose G --mesure 2026-11-28      # micro calibre a la place d'ecoute : remplace --spl
    python3 event.py calib 2026-11-28 --niveau 114   # apres avoir baisse le gain pour les paliers

- A refaire a chaque changement de gain du Scarlett ; chaque mesure garde la calibration en cours.
- Avec calibration, les paliers donnent le dB SPL au micro et l'analyse note la vitesse
  de l'air dans l'event (critere `vitesse_air_ms`, repere 17 m/s = 5 % de c).

Preampli et config CamillaDSP : chaque mesure lit la config active et enregistre le
gain fixe du canal (filtres Gain comme `preamp`, gains des mixers) ; les niveaux sont
compares en volume effectif (volume + gain de la config). Les paliers et la mesure du
bruit rose refusent une config qui fausserait la mesure : compresseur (`tube`),
loudness actif, sweep a moins de 3 dB du limiteur ou au-dessus de -1 dBFS
(`--accepter-config` pour passer outre). Les paliers s'arretent si le gain change en route.
`--spl V:SPL:GAIN` : le gain de config est affiche par `event.py rose G`.
  Sans lui, compression et distorsion sont jugees au palier le plus fort, et c'est ecrit.
- Sorties : `analyse/notes.md` et `analyse/notes.json`.

## Resultats

`resultats/` : resultats dates. `history/` : courbes avant/apres de septembre.

## Campagnes multi-niveaux (depuis le 18/11/2026)

    python3 campagne.py <etiquette> -36 -28 -21 -14 -8   # sweeps L, R + kick a chaque volume
    python3 analyse.py resultats/<campagne>              # effet du volume, ecart L/R, pics etroits
    python3 analyse.py resultats/<A> resultats/<B>       # B - A au meme volume
    python3 courbes.py page/courbes.json resultats/<base> resultats/<iteration> ...

- Loudness coupe pendant la campagne (puis restaure, ainsi que le volume) :
  on mesure l EQ seule.
- La montee s arrete si le micro depasse -1 dBFS (a -8 dB il sature : baisser
  le gain du Scarlett pour mesurer plus fort).
- Le module camilladsp n existe que dans ~/audio-power/venv (sans numpy) :
  campagne.py l appelle par ce python ; apply_iter.py se lance avec
  ~/audio-power/venv/bin/python3.
- page/ : page des courbes (sans correction / ancienne / nouvelle correction),
  publiee sur claude.ai ; courbes.json est regenere par courbes.py.
- Reference : resultats/2026-11-18_base-notches-actifs (tag git reglage-2026-11-18-base).

## Kick : reponses impulsionnelles et optimisation (18/11/2026)

Methode fiable (le clic enregistre directement n arrive que 10-14 dB au-dessus du
bruit de fond a la position d ecoute ; kick2.py reste un controle du corps) :

    ./reveil.sh                                   # reveille DAC + CamillaDSP
    curl -s "localhost:8080/vol?t=cdsp&db=-16"    # volume de mesure (micro < -4 dBFS)
    python3 ir2.py mesure <etiquette>             # reponses G et D, meme horloge
    python3 ir2.py predit <etiquette> filtre.param=valeur ...   # effet calcule
    python3 optim_kick.py <etiquette> [--bosse 4] [--clic 2]    # ~15 min, nohup conseille
    ./regle.py filtre.param=valeur ...            # appliquer en direct (perdu a la veille)
    ./restaure.py resultats/ir/<etiquette>.json   # revenir a l etat d une mesure
    python3 persiste.py resultats/ir/<etiquette>.json <suffixe>  # ecrire dans les YAML
    python3 kick_page.py page-kick/kick.json "<etiquette>:<nom>" ...

- ir2 : deux sweeps de 16 s decales de 1 s (G puis D) ; bruit ~-71 dB ; le kick a
  l oreille est calcule (kick x reponse), G+D = somme. Prediction verifiee a 0,1 dB.
- Indicateurs (coup G+D) : clic (energie 1,5-8 kHz / corps 40-120 Hz, vs fichier),
  bavure (aigu 6-40 ms apres le clic / clic), retard du corps (mi-hauteur, vs
  fichier), traine (tenue 60-300 ms vs fichier).
- Pieges : un retard "subsample" ajoute un passe-tout ; utiliser un nombre entier
  d echantillons (delay_L = 55 ech. = 1,25 ms). Les notches et autres reglages en
  direct sont perdus a chaque veille de CamillaDSP : les ecrire avec persiste.py.
- Resultats : k0_origine -> k8 (retard G entier) -> k9 (grave optimise, ecrit
  dans les YAML le 18/11 ; sauvegardes *.avant-kick-2026-11-18 sur le Pi).

## Fort volume, renfort du clic, FIR de phase (18/11/2026, apres-midi)

- Gain du Scarlett baisse d environ 25 dB : mesures possibles jusqu a 0 dB CamillaDSP.
  ./fort.sh <tag> -21 -11 -6 -3 0 : ir2 + kick2 a chaque palier. Resultat k9 :
  indicateurs du kick identiques de -21 a 0 dB, distorsion pendant le corps < -70 dB.
- k10 = k9 + click_boost 4,5 kHz +3,2 dB Q1,02 (au lieu de 2,6 kHz +2 dB Q3), ecrit
  dans les YAML (sauvegardes *.avant-renfort-2026-11-18). Clic G+D -2,2 -> +0,2 dB.
- fir.py : FIR passe-tout qui avance le grave (25-150 Hz), commun aux deux voies
  (--commun : calcule sur la somme G+D, garde la relation de phase G/D), retard
  global 60 ms, 16384 coefficients ; fichiers fir/phase_L.raw et phase_R.raw
  (copies de ~/camilladsp/fir). Prediction sur k10 : retard du corps G+D
  12,6 -> 6,7 ms. ./variante_fir.py on|off|check|etat pour l essayer en direct.
- FIR active le 18/11 (k11) : etape phase_grave [0, 1] avant le limiteur dans tous
  les YAML (sauvegardes *.avant-fir-2026-11-18). Mesure : retard du corps G+D
  12,6 -> 6,9 ms (ir2), 12,9 -> 5,6 ms (vrai kick) ; CamillaDSP ~10 % CPU.
  Bouton « Phase grave » dans l interface (etat lu en direct dans CamillaDSP) ;
  ./variante_fir.py contourne|actif fait la meme chose en ligne de commande.
  persiste_fir.py ajoute l etape aux YAML. tube/make_tube_config.py corrige
  (etape vide du limiteur, qui rendait les lampes impossibles a activer).
