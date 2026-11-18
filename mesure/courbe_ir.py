"""Ajoute a page/courbes.json une campagne calculee depuis des mesures ir2.

    python3 courbe_ir.py <etiquette affichee> <prefixe_ir> <vol1,vol2,...> [filtre.param=valeur ...]

Pour chaque volume : reponses G et D de resultats/ir/<prefixe_ir><vol>, avec les
changements de filtres donnes appliques (prediction exacte, ir2.apply_change),
recalees sur leur moyenne 200-1000 Hz, au format de courbes.py (mesure, brut, eq).
"""
import copy
import json
import sys

import numpy as np

import ir2
from courbes import CENTERS, eq_response
from sweep_dsp import band_average_db

label, prefix, vols = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
changes = [c for c in sys.argv[4:] if not c.startswith("--config=")]
cfg_from = [c.split("=", 1)[1] for c in sys.argv[4:] if c.startswith("--config=")]
page = json.load(open("page/courbes.json"))
f = np.array(CENTERS)
mid = (f >= 200) & (f <= 1000)
camp = {"etiquette": label, "date": None, "niveaux": {}}
clean = lambda a: [None if np.isnan(v) else round(float(v), 2) for v in a]
for v in vols:
    irs, meta = ir2.load(f"{prefix}{v}")
    new = copy.deepcopy(meta["config"])
    if cfg_from:                      # filtres d un autre reglage (ex. l origine) sur cette mesure
        other = json.load(open(cfg_from[0]))["config"]
        for n, flt in other["filters"].items():
            if n in new["filters"] and n not in ("loud_bass", "loud_treble"):
                new["filters"][n] = copy.deepcopy(flt)
    for c in changes:
        k, val = c.split("=")
        fl, p = k.split(".")
        new["filters"][fl]["parameters"][p] = float(val)
    irs2 = ir2.apply_change(irs, meta["config"], new)
    camp["date"] = meta["date"]
    entry = {}
    ref = (f >= 500) & (f <= 2500)
    absr, brut, eqs = {}, {}, {}
    for ch, idx in (("L", 0), ("R", 1)):
        x = irs2[ch]
        nf = 1 << (len(x) - 1).bit_length()
        X = np.fft.rfft(x, nf); fr = np.fft.rfftfreq(nf, 1 / ir2.FS)
        b = band_average_db(fr, 20 * np.log10(np.abs(X) + 1e-12), CENTERS, frac_octave=1 / 12)
        absr[ch] = np.array([b[c] if b[c] is not None else np.nan for c in CENTERS])
        eqs[ch] = eq_response(new, idx, f)
        brut[ch] = absr[ch] - eqs[ch]
    rm = np.nanmean(np.r_[absr["L"][ref], absr["R"][ref]])
    rb = np.nanmean(np.r_[brut["L"][ref], brut["R"][ref]])
    for ch in ("L", "R"):
        entry[ch] = {"mesure": clean(absr[ch] - rm), "brut": clean(brut[ch] - rb),
                     "eq": clean(eqs[ch] - np.mean(eqs[ch][ref])), "pic_micro": -20.0}
    entry["kick_ms"] = None
    camp["niveaux"][v] = entry
page["campagnes"] = [c for c in page["campagnes"] if c["etiquette"] != label] + [camp]
json.dump(page, open("page/courbes.json", "w"))
print("OK :", label, "niveaux", ", ".join(vols))
