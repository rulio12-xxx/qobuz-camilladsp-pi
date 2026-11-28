# Correction des enceintes : fichiers, generation et methode

Point d'entree unique pour retrouver la correction acoustique : ce qui est
actif, ou sont les fichiers (Pi et depot), avec quels scripts ils ont ete
generes et selon quelle methode. Les fichiers restent a leur place (les scripts
et services du Pi les attendent la) ; ce dossier les reference.

## Ou sont les fichiers

| Quoi | Sur le Pi | Dans le depot |
|---|---|---|
| Configs CamillaDSP actives (une par source) | `~/camilladsp/configs/camilladsp-{qobuz,bluetooth,fichiers,cd,vinyle}.yml`, `camilladsp.yml` (= copie de qobuz) | `camilladsp/` |
| Configs sans lampes (source de la regeneration lampes) | `~/camilladsp/configs/*.yml.avant-tube` | `camilladsp/*.yml.avant-tube` |
| FIR de phase du grave (float32, 44,1 kHz, 16384 coef.) | `~/camilladsp/fir/phase_L.raw`, `phase_R.raw` | `mesure/fir/` |
| Premieres configs REW (juillet 2026) | `~/camilladsp/configs/backup/` | `camilladsp/rew-history/`, `correction/archive-pi/backup-juillet-2026/` |
| Mesures REW brutes (.mdat) | PC : `C:\Users\heipp\REW\temp` | non (74 Mo) ; archive dans les fichiers du projet |
| Scripts de mesure et de generation | `~/audiohub/mesure/` (= le depot ; `~/bassmeasure` y pointe) | `mesure/` |
| Mesures et iterations datees | `~/audiohub/mesure/resultats/`, `iterations/`, `history/` | idem |
| Etage lampes | `~/tube/` | `tube/` |
| Sauvegardes avant chaque ecriture (`*.avant-kick-…`, `*.avant-fir-…`, `*.avant-retour-…`) | `~/camilladsp/configs/` | copie du 22/11 dans `correction/archive-pi/` (voir son README) |

Les filtres sont **identiques dans toutes les sources** ; seul le `preamp`
change (Qobuz/Fichiers/CD -20,5 dB, Vinyle -17,5 dB, Bluetooth -16,5 dB) et
le niveau de lampes.

## Reglages de reference (tags git)

| Tag / commit | Contenu |
|---|---|
| `lr-balance-v1` (7dfd342) | Equilibrage G/D a la nouvelle position d'ecoute (17 iterations du 09/10) |
| `reglage-2026-11-18-base` (b0ff8b3) | Base avant le travail sur le kick, notches 42/64 Hz actifs |
| `reglage-2026-11-18-kick-fir` (9554bac) | Grave optimise (k9), renfort du clic (k10), FIR de phase actif (k11), preamps +1 dB |
| `main` actuel (43d8580) | Retour a la base du 18/11 (e374de5) + `aigu_pente` (c5efd06) ; FIR hors service |

Restaurer un reglage : `git show <tag>:camilladsp/camilladsp-qobuz.yml`, ou
`mesure/restaure.py` / `mesure/persiste.py` a partir d'une mesure (voir plus bas).

Reglages **en direct, non ecrits dans les YAML** (perdus quand CamillaDSP recharge
sa config, reappliques par l'interface) : bouton Kick a trois niveaux dans
`hub/audio-hub.py` (`KICK_NIVEAUX` : gains `kick_body_L/R` sans 0/0, avec 4,0/3,5
= valeur des YAML, double 10,0/9,5 dB) et bouton Phase grave.

## Methode de generation (dans l'ordre historique)

0. **Premiere correction a la main (19/07)** : `archive-pi/backup-juillet-2026/camilladspClaude.yml`
   (passe-haut 28 Hz, Lowshelf 100 Hz +5 dB, coupes de modes).
1. **Correction de piece REW (juillet-septembre 2026)** : sweep au micro de mesure
   a la position d'ecoute, EQ automatique REW par voie -> filtres `filterL_1..16`
   et `filterR_0..12` (Peaking). Versions successives dans `camilladsp/rew-history/`,
   courbe cible dans `mesure/history/eq_target_20260923.json`.
2. **Equilibrage G/D (09/10)** : `measure_lr_bass.py` (20-1000 Hz) et
   `check_treble_centered.py` (500 Hz-16 kHz) ; chaque essai est un JSON
   `{"filtre": gain_dB}` applique par `apply_iter.py` puis remesure
   (`mesure/iterations/2026-10-09_equilibrage_LR/`). Puis aigu 8-14 kHz
   (`treble_air`, `ease_treble_rolloff.json`, `push_treble_air.json`).
3. **Resonances physiques** : `find_resonance.py` (sweep fin 20-160 Hz) ->
   `notch_42`, `notch_64` (-9 dB, Q 8) et `mode50_cut_L/R`.
4. **Kick (18/11)** : `ir2.py mesure` (reponses impulsionnelles G et D, meme
   horloge), `ir2.py predit` (effet calcule d'un changement, verifie a 0,1 dB),
   `optim_kick.py` (optimisation des filtres du grave sur les indicateurs clic /
   bavure / retard du corps / traine), `persiste.py` pour ecrire dans les YAML.
   Campagnes multi-niveaux : `campagne.py`, `analyse.py`, `fort.sh`.
5. **FIR de phase du grave (18/11)** : `fir.py <etiquette_ir> --commun --ecrire`.
   Retard de groupe de chaque enceinte (relatif a l'aigu), lisse au 1/3 d'octave
   entre 25 Hz et 250 Hz ; le FIR passe-tout avance le grave de 80 % de ce retard
   sans changer le niveau ; retard global de 60 ms commun aux deux voies pour
   rendre le filtre realisable ; calcule sur la somme G+D (`--commun`) pour garder
   la relation de phase G/D. Ajout aux YAML : `persiste_fir.py` ; essai en direct :
   `variante_fir.py on|off|check|etat`.
6. **Pente d'aigu (20/11)** : `ajoute_pente.py` -> `aigu_pente` (Highshelf 2,5 kHz,
   -1,5 dB, Q 0,5) dans sa propre etape commune.
7. **Lampes** : `tube/apply_tube.sh <niveau>` regenere les YAML actifs depuis les
   `*.avant-tube` avec `make_tube_config.py` (verification `camilladsp --check`
   avant de remplacer). Toute modification de filtre doit donc aussi aller dans
   les `*.avant-tube` (`persiste.py` le fait).

Details des mesures et des pieges : `mesure/README.md`.
Tous les renforts / variantes du grave essayes, avec leurs valeurs : `variantes_grave.md`
(regenerable avec `historique_grave.py`).

## Garder le Pi et git synchronises

Sur le Pi :

    cd ~/audiohub
    ./correction/inventaire_pi.sh   # lecture seule : ce qui differe ou manque dans git
    ./sync.sh                       # copie configs (dont CD/Vinyle) et FIR dans le depot
    git add -A && git commit -m "..." && git push

Tableau des filtres d'une config : `python3 correction/tableau_filtres.py camilladsp/camilladsp-qobuz.yml`.

## Filtres actifs (camilladsp-qobuz.yml, main 43d8580)

| Etape | Voie | Filtre | Type | Freq (Hz) | Gain (dB) | Q |
|---|---|---|---|---|---|---|
| 1 | G | preamp | Gain | | -20.5 | |
| 1 | G | mode50_cut_L | Peaking | 50 | -10.0 | 4.5 |
| 1 | G | notch_42 | Peaking | 42 | -9.0 | 8.0 |
| 1 | G | notch_64 | Peaking | 64 | -9.0 | 8.0 |
| 1 | G | kick_body_L | Peaking | 80 | 4.0 | 4.0 |
| 1 | G | click_boost | Peaking | 2600 | 2.0 | 3.0 |
| 1 | G | filterL_1 | Peaking | 56.1 | -3.0 | 5.381 |
| 1 | G | filterL_2 | Peaking | 70.5 | -0.5 | 2.992 |
| 1 | G | filterL_3 | Peaking | 93.2 | -7.9 | 4.272 |
| 1 | G | filterL_4 | Peaking | 113.5 | 4.5 | 4.477 |
| 1 | G | filterL_5 | Peaking | 124.0 | 0.0 | 7.419 |
| 1 | G | filterL_6 | Peaking | 160.5 | -11.5 | 4.542 |
| 1 | G | filterL_7 | Peaking | 231.0 | 1.5 | 6.877 |
| 1 | G | filterL_8 | Peaking | 244.0 | -4.7 | 4.911 |
| 1 | G | filterL_9 | Peaking | 328.0 | -5.3 | 2.907 |
| 1 | G | filterL_10 | Peaking | 406.0 | -4.2 | 4.999 |
| 1 | G | filterL_11 | Peaking | 504.0 | 5.5 | 1.212 |
| 1 | G | filterL_12 | Peaking | 905.0 | 1.5 | 5.0 |
| 1 | G | filterL_13 | Peaking | 1494.0 | -3.2 | 1.052 |
| 1 | G | filterL_14 | Peaking | 1948.0 | 7.0 | 5.621 |
| 1 | G | filterL_15 | Peaking | 3258.0 | -3.1 | 4.193 |
| 1 | G | filterL_16 | Peaking | 7427.0 | 2.5 | 2.793 |
| 1 | G | treble_air | Peaking | 11800 | 4.5 | 3.0 |
| 1 | G | balance_L | Peaking | 790 | -2.3 | 0.55 |
| 1 | G | delay_L | Delay | | 1.2 ms | |
| 1 | G | loud_bass | Peaking | 80 | 0.0 | 4.0 |
| 1 | G | loud_treble | Peaking | 3500 | 0.0 | 1.2 |
| 2 | D | preamp | Gain | | -20.5 | |
| 2 | D | kick_fill_R | Peaking | 70 | 3.2 | 1.8 |
| 2 | D | mode50_cut_R | Peaking | 50 | -10.0 | 5.5 |
| 2 | D | notch_42 | Peaking | 42 | -9.0 | 8.0 |
| 2 | D | notch_64 | Peaking | 64 | -9.0 | 8.0 |
| 2 | D | kick_body_R | Peaking | 80 | 3.5 | 4.0 |
| 2 | D | click_boost | Peaking | 2600 | 2.0 | 3.0 |
| 2 | D | filterR_0 | Peaking | 56.0 | 2.0 | 3.5 |
| 2 | D | filterR_01 | Peaking | 64.0 | 16.5 | 6.0 |
| 2 | D | filterR_1 | Peaking | 150.0 | 1.8 | 7.18 |
| 2 | D | filterR_2 | Peaking | 223.0 | -3.0 | 2.791 |
| 2 | D | filterR_3 | Peaking | 304.0 | 2.5 | 4.999 |
| 2 | D | filterR_4 | Peaking | 447.0 | -4.6 | 3.907 |
| 2 | D | filterR_5 | Peaking | 501.0 | 5.8 | 7.496 |
| 2 | D | filterR_6 | Peaking | 663.0 | 3.1 | 6.966 |
| 2 | D | filterR_7 | Peaking | 1013.0 | -4.3 | 2.385 |
| 2 | D | filterR_8 | Peaking | 1632.0 | -4.5 | 3.217 |
| 2 | D | filterR_9 | Peaking | 2248.0 | 1.8 | 7.493 |
| 2 | D | filterR_10 | Peaking | 3478.0 | -2.4 | 2.629 |
| 2 | D | filterR_11 | Peaking | 5587.0 | 2.6 | 7.308 |
| 2 | D | filterR_12 | Peaking | 7501.0 | 0.5 | 1.821 |
| 2 | D | treble_air | Peaking | 11800 | 4.5 | 3.0 |
| 2 | D | kick | Peaking | 180 | -2.5 | 0.9 |
| 2 | D | delay_R | Delay | | 0 ms | |
| 2 | D | loud_bass | Peaking | 80 | 0.0 | 4.0 |
| 2 | D | loud_treble | Peaking | 3500 | 0.0 | 1.2 |
| 3 | G+D | aigu_pente | Highshelf | 2500 | -1.5 | 0.5 |
| 4 | G+D | tube | processeur | | | |
| 5 | G+D | limiter | Limiter | | | |
