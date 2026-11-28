#!/usr/bin/env python3
"""Ecrit le reglage « creux recurrents » (valide a l'ecoute le 22/11/2026) dans les YAML.

    python3 correction/test-creux/persiste_creux.py <dossier_configs> [--essai]

Modifie camilladsp{,-qobuz,-fichiers,-bluetooth,-cd,-vinyle}.yml et les *.avant-tube
(base des lampes) presents dans le dossier, en gardant la mise en forme :
- mode50_cut_L : 50 Hz -10 dB -> 55 Hz -7 dB
- voie G : notch_64 retire, notch_42 remplace par notch_42_L (-4 dB Q8),
  + creux_L_80 (+8 Q6), creux_L_120 (+9 Q6) avant delay_L
- voie D : + creux_R_130 (+9 Q5), creux_R_182 (+10 Q6), creux_R_47 (+8 Q3),
  bosse_R_152 (-7 Q6), bosse_R_104 (-5 Q4) avant delay_R
Un fichier deja modifie (filtre creux_L_80 present) est ignore.
"""
import os
import re
import sys

NOMS = ["camilladsp.yml", "camilladsp-qobuz.yml", "camilladsp-fichiers.yml",
        "camilladsp-bluetooth.yml", "camilladsp-cd.yml", "camilladsp-vinyle.yml",
        "camilladsp-qobuz.yml.avant-tube", "camilladsp-fichiers.yml.avant-tube",
        "camilladsp-bluetooth.yml.avant-tube"]
NOUVEAUX = [("notch_42_L", 42, -4.0, 8.0), ("creux_L_80", 80, 8.0, 6.0), ("creux_L_120", 120, 9.0, 6.0),
            ("creux_R_47", 47, 8.0, 3.0), ("creux_R_130", 130, 9.0, 5.0), ("creux_R_182", 182, 10.0, 6.0),
            ("bosse_R_104", 104, -5.0, 4.0), ("bosse_R_152", 152, -7.0, 6.0)]
G = ["notch_42_L", "creux_L_80", "creux_L_120"]
D = ["creux_R_47", "creux_R_130", "creux_R_182", "bosse_R_104", "bosse_R_152"]


def transforme(t):
    if "creux_L_80:" in t:
        return None
    # mode50_cut_L
    t, n = re.subn(r"(  mode50_cut_L:\n    type: Biquad\n    parameters:\n      type: Peaking\n)      freq: 50\n      gain: -10.0\n",
                   r"\1      freq: 55\n      gain: -7.0\n", t)
    assert n == 1, "mode50_cut_L introuvable ou deja different"
    # definitions, juste apres "filters:"
    defs = "".join(f"  {nom}:\n    type: Biquad\n    description: creux recurrents (22/11/2026)\n    parameters:\n"
                   f"      type: Peaking\n      freq: {f}\n      gain: {g}\n      q: {q}\n" for nom, f, g, q in NOUVEAUX)
    t = t.replace("\nfilters:\n", "\nfilters:\n" + defs, 1)
    # voie G : premiere occurrence (avant delay_L)
    iL = t.index("      - delay_L\n")
    gauche, reste = t[:iL], t[iL:]
    k = gauche.rindex("    channels: [0]")
    seg = gauche[k:]
    assert "      - notch_42\n" in seg and "      - notch_64\n" in seg
    seg = seg.replace("      - notch_42\n", "", 1).replace("      - notch_64\n", "", 1)
    seg += "".join(f"      - {n}\n" for n in G)
    t = gauche[:k] + seg + reste
    iR = t.index("      - delay_R\n")
    t = t[:iR] + "".join(f"      - {n}\n" for n in D) + t[iR:]
    return t


def main():
    d = sys.argv[1]
    essai = "--essai" in sys.argv
    for nom in NOMS:
        p = os.path.join(d, nom)
        if not os.path.exists(p):
            continue
        t = open(p).read()
        n = transforme(t)
        if n is None:
            print(f"deja fait : {nom}")
            continue
        if not essai:
            open(p, "w").write(n)
        print(f"{'essai' if essai else 'ecrit'} : {nom}")


main()
