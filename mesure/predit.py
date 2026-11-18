"""Predit la reponse apres changement de filtres, a partir d'une mesure.

    python3 predit.py resultats/<campagne> filtre.param=valeur ...

nouvelle reponse = mesure - reponse calculee des filtres de la mesure
                             + reponse calculee des filtres modifies
(exact pour des filtres lineaires ; la piece ne change pas). Affiche le grave
30-250 Hz de G, D et G-D, avant -> apres, relatif a la moyenne 200-1000 Hz.
"""
import copy
import json
import os
import sys

import numpy as np

from courbes import eq_response, CENTERS

d = sys.argv[1]
changes = sys.argv[2:]
res = json.load(open(os.path.join(d, "niveaux.json")))
cfg = json.load(open(os.path.join(d, "config_active.json")))["config"]
new = copy.deepcopy(cfg)
for c in changes:
    k, v = c.split("=")
    f, p = k.split(".")
    new["filters"][f]["parameters"][p] = float(v)
vol = sorted(res["niveaux"], key=float)[-1]
f = np.array(CENTERS)
mid = (f >= 200) & (f <= 1000)
out = {}
for ch, idx in (("L", 0), ("R", 1)):
    m = np.array([np.nan if v is None else v for v in res["niveaux"][vol][ch]["bands_12"]])
    before = m - np.nanmean(m[mid])
    after = m - eq_response(cfg, idx, f) + eq_response(new, idx, f)
    after = after - np.nanmean(after[mid])
    out[ch] = (before, after)

print(f"Prediction a {vol} dB : {' '.join(changes) or '(aucun changement)'}")
print("   Hz     G avant->apres     D avant->apres    G-D avant->apres")
sel = [i for i, x in enumerate(f) if 30 <= x <= 250]
for i in sel:
    bl, al = out["L"][0][i], out["L"][1][i]
    br, ar = out["R"][0][i], out["R"][1][i]
    print(f"  {f[i]:5.0f}  {bl:+6.1f} -> {al:+6.1f}   {br:+6.1f} -> {ar:+6.1f}   {bl-br:+6.1f} -> {al-ar:+6.1f}")
band = [i for i in sel if 45 <= f[i] <= 200]
for name, k in (("avant", 0), ("apres", 1)):
    lr = np.array([out["L"][k][i] - out["R"][k][i] for i in band])
    dev = np.array([np.r_[out["L"][k][i], out["R"][k][i]] for i in band]).ravel()
    print(f"{name} : ecart G-D 45-200 Hz moyen {np.nanmean(np.abs(lr)):.1f} dB (max {np.nanmax(np.abs(lr)):.1f}), "
          f"ecart a plat {np.nanmean(np.abs(dev)):.1f} dB (max {np.nanmax(np.abs(dev)):.1f})")
