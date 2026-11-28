# Test : renfort des creux recurrents du grave (22/11/2026)

Config d'essai, **pas active** : `camilladsp-qobuz-test-creux.yml` = `camilladsp-qobuz.yml`
(main 43d8580) + les changements ci-dessous. Les configs actives ne sont pas modifiees.

## Creux recurrents (creux.py)

24 mesures du 18/11 (16 reponses impulsionnelles dans la journee + campagnes a 5 volumes),
correction retiree. Toutes au meme point d'ecoute : elles prouvent que les creux sont
stables (pas du bruit), pas qu'ils restent quand le micro bouge. Recoupement avec juillet
(autre position) : l'EQ auto REW avait deja releve G ~113 Hz (+4,5) et D 56-64 Hz (+6).

| Voie | Creux (brut) | Present dans | Deja corrige ? |
|---|---|---|---|
| G | 80 Hz -6 | 96 % | non (reste -5) |
| G | 120 Hz -8 | 96 % (+ REW juillet) | non (reste -7,5) |
| G | 42-67 Hz | sur-coupe par la correction (notches + mode 50 Hz) | creuse a -10/-12 |
| D | 45-50 Hz -7/-8 | 90 % | non (reste -12) |
| D | 60-64 Hz -10 | 100 % (+ REW juillet) | oui, +9 dB (reste -3 : annulation de piece) |
| D | 75-80 Hz -13/-10 | 100 % | oui, +9 dB (reste -3/-2) |
| D | 127-134 Hz -6 | 90 % | non |
| D | 180-190 Hz -9/-5 | 60-90 % | non (reste -11) |

## Changements du test

- G : `mode50_cut_L` 50 Hz -10 -> 55 Hz -7 (vise la bosse 53-57 Hz) ; `notch_64` retire a gauche
  (pas de bosse a 64 Hz a gauche) ; `notch_42` remplace a gauche par `notch_42_L` -4 dB ;
  `creux_L_80` +4 dB Q6 ; `creux_L_120` +5 dB Q6.
- D : `creux_R_47` +4 dB Q3 ; `creux_R_130` +5 dB Q5 ; `creux_R_182` +6 dB Q6 ;
  et pour que ces renforts ne debordent pas : `bosse_R_104` -5 dB Q4, `bosse_R_152` -7 dB Q6
  (bosses de +7/+10 dB jamais corrigees).
- Renfort maxi +6 dB par filtre (regle du 23/09). Le reste (preamp, lampes, pente d'aigu) est inchange.

## Effet calcule (test.py, sur la mesure k0_origine, ref 200-1000 Hz)

| | Ecart-type 40-300 Hz actuel | test |
|---|---|---|
| Gauche | 6,7 dB | 5,2 dB |
| Droite | 7,2 dB | 5,7 dB |
| G+D | 7,5 dB | 7,0 dB |

G : 42-67 Hz remonte de -10/-16 a -3/-9 ; 80 Hz -5 -> 0 ; 120 Hz -7,5 -> -2,5.
D : 47 Hz -13 -> -9 ; 127-134 Hz -6 -> -4 ; 180 Hz -11 -> -7 ; bosses 100 Hz +9 -> +5, 151 Hz +10 -> +5,5.
Limite : a 60 Hz, la somme G+D se creuse (-9 -> -14) : G et D s'y annulent en phase,
une EQ ne peut pas corriger ca.

## Essayer

Sur la Pi, copier le fichier dans `~/camilladsp/configs/`, puis le charger dans l'interface
CamillaDSP (camillagui) ; revenir avec `camilladsp-qobuz.yml`, ou changer de source (le
selecteur recharge la config normale). Ensuite remesurer :
`cd ~/audiohub/mesure && python3 ir2.py mesure test-creux` et comparer a `k0_origine`.

## Adopte et renforce (22/11/2026, apres-midi)

Valide a l'ecoute (« on garde »), puis renforce deux fois de +2 dB a la demande :
creux_L_80 +8, creux_L_120 +9, creux_R_47 +8, creux_R_130 +9, creux_R_182 +10 dB
(frequences, Q et bosses inchanges). Ecrit dans les 6 configs et les 3 `*.avant-tube`.

- Saturation : 0 echantillon ecrete sur 30 s de Qobuz ; crete de sortie -34 / -33 dBFS au
  volume -22 (entree a -0,1 dBFS). Gain d'EQ maxi : D 64 Hz +12 dB (ancien renfort), G 120 Hz +9,9 dB.
- Effet calcule (ecart-type 40-300 Hz) : G 6,7 -> 5,2 (+4/+5) -> 5,6 (+8/+9) : la gauche
  depasse vers 80 et 127 Hz (+3,6 / +4,7 dB) ; D 7,2 -> 5,7 -> 5,2. Si la gauche parait
  trop grasse : creux_L_80 +4, creux_L_120 +5.
