"""Analyse d'une campagne (campagne.py), ou comparaison de deux campagnes.

    python3 analyse.py resultats/<campagne>                 # analyse seule
    python3 analyse.py resultats/<A> resultats/<B>          # B - A, meme volume

Analyse seule :
  1. Dependance au niveau : chaque courbe est recalee de l'ecart de volume par
     rapport au niveau de reference (-21 dB si present) ; ce qui reste est ce qui
     change vraiment avec le niveau (piece, meuble, compression des HP).
  2. Ecart L/R par bande, a chaque niveau.
  3. Pics etroits en 20-200 Hz (1/12 oct) : bande > mediane des voisines
     (+-1/3 oct) de plus de SEUIL_PIC dB -> resonance probable.
  4. Kick : chute -20 dB par niveau.
"""
import json
import os
import sys

import numpy as np

REF_VOL = "-21"
SEUIL_PIC = 4.0
BANDS_SHOW = ["20", "25", "31.5", "40", "50", "63", "80", "100", "125", "160", "200",
              "250", "315", "400", "500", "630", "800", "1000", "1250", "1600", "2000",
              "2500", "3150", "4000", "5000", "6300", "8000", "10000", "12500", "16000"]


def load(d):
    with open(os.path.join(d, "niveaux.json")) as f:
        return json.load(f)


def vols_of(res):
    return sorted(res["niveaux"].keys(), key=float)


def mid_ref(bands):
    """Niveau moyen 200-1000 Hz, sert de reference de niveau absolue."""
    v = [bands[b] for b in ("200", "250", "315", "400", "500", "630", "800", "1000")
         if bands.get(b) is not None]
    return float(np.mean(v))


def table(title, cols, rows):
    print(f"\n{title}")
    print(f"{'Hz':>6} " + " ".join(f"{c:>7}" for c in cols))
    for name, vals in rows:
        print(f"{name:>6} " + " ".join(f"{v:>+7.1f}" if v is not None else f"{'-':>7}" for v in vals))


def peaks(lf):
    fs = sorted(int(k) for k in lf if lf[k] is not None)
    out = []
    for f in fs:
        neigh = [lf[str(g)] for g in fs if g != f and f / 1.26 <= g <= f * 1.26
                 and abs(g - f) > 2 and lf[str(g)] is not None]
        if len(neigh) < 3:
            continue
        ex = lf[str(f)] - float(np.median(neigh))
        if ex >= SEUIL_PIC:
            out.append((f, round(ex, 1)))
    # garder le max local de chaque groupe
    res = []
    for f, ex in out:
        if res and f - res[-1][0] <= 4:
            if ex > res[-1][1]:
                res[-1] = (f, ex)
        else:
            res.append((f, ex))
    return res


def analyse(d):
    res = load(d)
    vols = vols_of(res)
    ref = REF_VOL if REF_VOL in vols else vols[len(vols) // 2]
    print(f"Campagne {res['etiquette']} ({res['date']}), niveaux {', '.join(vols)} dB, reference {ref} dB")

    for ch in ("L", "R"):
        refb = res["niveaux"][ref][ch]["bands_3"]
        rows = []
        for b in BANDS_SHOW:
            vals = []
            for v in vols:
                cur = res["niveaux"][v][ch]["bands_3"]
                if cur.get(b) is None or refb.get(b) is None:
                    vals.append(None); continue
                vals.append(cur[b] - refb[b] - (float(v) - float(ref)))
            rows.append((b, vals))
        table(f"[{ch}] Ecart a la courbe de reference {ref} dB, ecart de volume retire "
              f"(0 = la piece/les HP se comportent pareil a ce niveau)", vols, rows)

    rows = []
    for b in BANDS_SHOW:
        vals = []
        for v in vols:
            L = res["niveaux"][v]["L"]["bands_3"]; R = res["niveaux"][v]["R"]["bands_3"]
            vals.append(L[b] - R[b] if L.get(b) is not None and R.get(b) is not None else None)
        rows.append((b, vals))
    table("Ecart L - R par niveau (dB)", vols, rows)

    rows = []
    for b in BANDS_SHOW:
        vals = []
        for v in vols:
            for ch in ("L", "R"):
                B = res["niveaux"][v][ch]["bands_3"]
                vals.append(B[b] - mid_ref(B) if B.get(b) is not None else None)
        rows.append((b, vals))
    table("Courbe de chaque voie relative a sa moyenne 200-1000 Hz",
          [f"{v}{ch}" for v in vols for ch in ("L", "R")], rows)

    print("\nPics etroits 20-200 Hz (exces sur les voisines +-1/3 oct, seuil "
          f"{SEUIL_PIC} dB) :")
    for v in vols:
        for ch in ("L", "R"):
            p = peaks(res["niveaux"][v][ch]["bands_lf"])
            txt = ", ".join(f"{f} Hz (+{ex} dB)" for f, ex in p) or "aucun"
            print(f"  {v:>4} dB {ch} : {txt}")

    print("\nKick (chute -20 dB, bande 40-120 Hz) :")
    for v in vols:
        k = res["niveaux"][v]["kick"]
        print(f"  {v:>4} dB : {k['decay_ms']} ms (source {k['src_decay_ms']} ms), "
              f"pic micro {k['peak_dbfs']:+.1f} dBFS")
    print("\nPics micro (sweeps) : " + ", ".join(
        f"{v}: L {res['niveaux'][v]['L']['peak_dbfs']:+.1f} / R {res['niveaux'][v]['R']['peak_dbfs']:+.1f}"
        for v in vols))


def compare(da, db):
    A, B = load(da), load(db)
    common = [v for v in vols_of(A) if v in B["niveaux"]]
    print(f"Comparaison {B['etiquette']} - {A['etiquette']}, niveaux communs {', '.join(common)} dB")
    for ch in ("L", "R"):
        rows = []
        for b in BANDS_SHOW:
            vals = []
            for v in common:
                a = A["niveaux"][v][ch]["bands_3"].get(b); c = B["niveaux"][v][ch]["bands_3"].get(b)
                vals.append(c - a if a is not None and c is not None else None)
            rows.append((b, vals))
        table(f"[{ch}] Difference (dB)", common, rows)
    rows = []
    for b in BANDS_SHOW:
        vals = []
        for v in common:
            for X in (A, B):
                L = X["niveaux"][v]["L"]["bands_3"].get(b); R = X["niveaux"][v]["R"]["bands_3"].get(b)
                vals.append(L - R if L is not None and R is not None else None)
        rows.append((b, vals))
    table("Ecart L - R : A puis B par niveau", [f"{v}{x}" for v in common for x in ("A", "B")], rows)
    print("\nKick (ms) :")
    for v in common:
        print(f"  {v:>4} dB : A {A['niveaux'][v]['kick']['decay_ms']} -> B {B['niveaux'][v]['kick']['decay_ms']}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        analyse(sys.argv[1])
    else:
        compare(sys.argv[1], sys.argv[2])
