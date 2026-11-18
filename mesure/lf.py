"""Resume du grave d'une campagne : G, D et G-D en 1/12 oct de 30 a 250 Hz,
relatifs a la moyenne 200-1000 Hz de chaque voie.

    python3 lf.py resultats/<campagne> [volume]
"""
import json
import os
import sys

d = sys.argv[1]
r = json.load(open(os.path.join(d, "niveaux.json")))
vol = sys.argv[2] if len(sys.argv) > 2 else sorted(r["niveaux"], key=float)[-1]
lv = r["niveaux"][vol]


def rel(ch):
    b3 = lv[ch]["bands_3"]
    ref = sum(b3[k] for k in ("200", "250", "315", "400", "500", "630", "800", "1000")) / 8
    return {int(k): v - ref for k, v in lv[ch]["bands_lf"].items() if v is not None}


L, R = rel("L"), rel("R")
print(f"Grave a {vol} dB (0 = moyenne 200-1000 Hz)")
print("   Hz      G      D    G-D")
for f in (30, 34, 38, 42, 46, 50, 54, 58, 62, 66, 70, 74, 80, 86, 92, 100, 108, 116, 126, 136, 146, 152, 160, 170, 184, 200):
    if f in L and f in R:
        print(f"  {f:3d} {L[f]:+6.1f} {R[f]:+6.1f} {L[f]-R[f]:+6.1f}")
