# Renforts et variantes du grave par EQ (juillet - novembre 2026)

Tous les essais de renfort / reglage du grave qui ont ete ecrits dans git, dans
l'ordre. Valeurs : type, frequence (Hz), gain (dB), Q. Tableau complet et a jour :
`python3 correction/historique_grave.py` (lit l'historique git, rien n'est modifie).

Pour ecouter de nouveau une variante : `git show <commit>:camilladsp/camilladsp-qobuz.yml`
donne la config complete ; les valeurs se reportent avec `mesure/regle.py filtre.param=valeur`
(en direct) ou `mesure/persiste.py` (dans les YAML).

## 0. Premiere correction a la main (19/07, avant REW)

`correction/archive-pi/backup-juillet-2026/camilladspClaude.yml` : headroom -6 dB,
passe-haut 28 Hz (Butterworth ordre 4), **renfort Lowshelf 100 Hz +5 dB Q0,7** sur les
deux voies, coupes de modes G 55 Hz -9, 93 Hz -4, 160 Hz -5 ; D 151 Hz -6, 215 Hz -3,5.

## 1. Correction REW d'origine (25/07, 6f654cd)

EQ automatique REW. Renforts : `filterL_2` 70,5 Hz +6 dB Q3, `filterL_4` 113,5 Hz +4,5 dB,
`filterR_0` 56 Hz +6 dB Q3,5, `filterR_01` 64 Hz +6 dB Q6. Coupes : `filterL_3` 93 Hz -7,9,
`filterL_5` 124 Hz -4,9, `filterL_6` 160 Hz -8,1, `filterR_1` 150 Hz -5. Preamp -16 dB.

## 2. Kick 180 Hz et premiere baisse (23/08 - 01/09)

- 5dd3137 : `kick` (voie D) 180 Hz -2,5 dB Q0,9 (desengorge le haut-grave), preamp -14 dB.
- 5176921 : les trois renforts 56 / 64 / 70 Hz de +6 a +5,5 dB (grave un peu fort a l'ecoute).

## 3. Loudness (13/09, bf90106)

`loud_bass` Lowshelf 120 Hz, gain pilote par `loudness/loudness.py` selon le volume.
Devenu Peaking 80 Hz Q4 le 09/10.

## 4. « Grave sec + kick » par voie (23/09, 0997afc ; 30/09, 77b05e7)

Mesure par voie isolee (sweep + deconvolution).
- `mode50_cut_L` 50 Hz Q4,5 : -5 -> -7 (23/09) -> -9 dB (30/09)
- `mode50_cut_R` 50 Hz Q5,5 : -10 -> -12 (23/09) -> -14 dB (30/09)
- `kick_fill_R` 70 Hz +6 dB Q1,8 : comble le creux 63-80 Hz de la voie D (plafond +6 dB)
- preamp -14 -> -21 puis -20,5 dB (marge sous le limiteur avec loudness + lampes)
- Projection avant/apres : `mesure/history/eq_target_20260923.json`.

## 5. Bouton Kick « kick_body » 80 Hz Q4 (30/09 - 10/10)

| Date | Commit | Gauche | Droite | Commentaire |
|---|---|---|---|---|
| 30/09 | 0427e5d | +1,5 | +1,5 | bouton en direct (`KICKBODY_GAIN`) |
| 09/10 | 7dfd342 | +3,0 | +2,5 | apres equilibrage G/D |
| 09/10 | 1337aa4 | +4,0 | +3,5 | +1 dB, valeur « avec » actuelle |
| 10/10 | bfbab7d, 35ed04b | | | curseur « Kick Hz » (50-120 puis 70-120 Hz), retire le 18/11 |

## 6. Equilibrage G/D a la nouvelle position (09/10, 7dfd342, tag `lr-balance-v1`)

`filterL_2` +5,5 -> -0,5 ; `filterL_5` -4,9 -> 0 ; `filterL_6` -8,1 -> -11,5 ;
`filterR_0` +5,5 -> +2 ; **`filterR_01` 64 Hz +5,5 -> +16,5 dB Q6** ; `filterR_1` -5 -> +1,8 ;
`kick_fill_R` +6 -> +3,2 ; `mode50_cut_L` -10 ; `mode50_cut_R` -14 -> -10.
Puis a4d8e34 : `notch_42` et `notch_64` -9 dB Q8 sur les deux voies (resonances physiques).
Iterations detaillees : `mesure/iterations/2026-10-09_equilibrage_LR/`.

## 7. Grave optimise sur le kick (18/11, 8004723 -> b3479f5, tag `reglage-2026-11-18-kick-fir`)

Optimisation automatique (`mesure/optim_kick.py`) sur reponses impulsionnelles :

| Filtre | Avant | Optimise (k9) |
|---|---|---|
| filterL_1 | 56,1 Hz -3,0 Q5,4 | 57,4 Hz -3,4 Q4,9 |
| filterL_2 | 70,5 Hz -0,5 Q3,0 | 81,1 Hz +5,8 Q5,1 |
| filterL_3 | 93,2 Hz -7,9 Q4,3 | 93,2 Hz -14,2 Q5,0 |
| filterL_4 | 113,5 Hz +4,5 Q4,5 | 121,1 Hz +4,8 Q5,0 |
| filterL_5 | 124 Hz 0 Q7,4 | 135,9 Hz -6,3 Q5 |
| filterL_6 | 160,5 Hz -11,5 Q4,5 | 216,2 Hz -7,4 Q1 |
| filterL_8 | 244 Hz -4,7 | 184,9 Hz -7,8 Q5,0 |
| filterR_0 | 56 Hz +2,0 Q3,5 | 76,8 Hz +5 Q5,1 |
| filterR_01 | 64 Hz +16,5 Q6 | 60,9 Hz +4 Q5,1 |
| filterR_1 | 150 Hz +1,8 Q7,2 | 154,8 Hz -3,1 Q5,1 |
| kick (D) | 180 Hz -2,5 Q0,9 | 106,5 Hz -9,1 Q5,4 |
| kick_body_L | 80 Hz +4,0 Q4 | 73 Hz +4,8 Q0,82 |
| kick_body_R | 80 Hz +3,5 Q4 | 77,3 Hz +5,8 Q5 |
| kick_fill_R | 70 Hz +3,2 Q1,8 | 46,7 Hz +6 Q1,86 |
| mode50_cut_L | 50 Hz -10 Q4,5 | 55,2 Hz -6 Q4,9 |
| mode50_cut_R | 50 Hz -10 Q5,5 | 56,2 Hz -2,4 Q5,0 |
| notch_42 / 64 | -9 | 0 (puis -9 remis en b3479f5) |

Plus : `click_boost` 4,5 kHz +3,2 dB Q1,02 (k10), FIR de phase du
grave (k11). b3479f5 : kick « normal » = valeurs optimisees, bouton = renfort +3 dB
(G 7,8 / D 8,8), preamps +1 dB (-19,5).

Abandonne le 20/11 (e374de5, a la demande) : retour au reglage du 09/10.

## 8. Bouton Kick a trois niveaux (20/11, actuel)

Reglage en direct de `kick_body_L/R` (80 Hz Q4) par l'interface (`hub/audio-hub.py`, `KICK_NIVEAUX`) :

| Niveau | Gauche | Droite |
|---|---|---|
| sans | 0 | 0 |
| avec (= YAML) | +4,0 | +3,5 |
| double | +9,0 / +8,5 (4da876a) puis **+10,0 / +9,5** (43d8580) |

## Sauvegardes de la Pi

Toutes les sauvegardes `*.avant-*` de la Pi (etat avant chaque changement des 18 et
20/11, etc.) sont dans `correction/archive-pi/sauvegardes-configs/`.

## Non retrouve dans git

Les essais faits seulement en direct dans une conversation (`regle.py`, `apply_iter.py`)
sans etre ecrits dans les YAML ne sont pas dans l'historique. Sur le Pi, il peut en rester
des traces dans `~/camilladsp/configs/*.avant-*` (sauvegardes) et `mesure/resultats/ir/*.json`
(etat des filtres au moment de chaque mesure, relisible avec `mesure/restaure.py`).
