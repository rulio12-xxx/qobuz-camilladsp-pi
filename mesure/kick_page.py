"""Donnees de la page « Kick a l'oreille » depuis des mesures ir2.

    python3 kick_page.py <sortie.json> <etiquette_ir:nom affiche> ...

Pour chaque reglage : kick simule (G, D, G+D) = enveloppes du clic et du corps,
indicateurs, et grave 30-250 Hz de G et D (1/12 oct).
"""
import json
import sys

import numpy as np

import ir2

out = {"reglages": []}
src_env = None
for arg in sys.argv[2:]:
    label, name = arg.split(":", 1)
    irs, meta = ir2.load(label)
    m, _ = ir2.kick_metrics(irs)
    r = ir2.responses(irs)
    fc = np.array(ir2.CENTERS)
    sel = (fc >= 30) & (fc <= 250)
    src_env = m["source"]["enveloppes"]
    t_ms = m["G"]["enveloppes"]["t_ms"]
    entry = {"etiquette": label, "nom": name, "date": meta["date"], "ecart_GD_ms": m["ecart_GD_ms"],
             "types": {}, "grave": {"f": fc[sel].round(1).tolist(),
                                    "G": np.round(r["L"][sel], 2).tolist(),
                                    "D": np.round(r["R"][sel], 2).tolist(),
                                    "GD": np.round(r["GD"][sel], 2).tolist()}}
    for t in ("G", "D", "GD"):
        e = m[t]
        entry["types"][t] = {k: e[k] for k in ("clic_rel_db", "bavure_db", "corps_retard_ms", "traine_db")}
        entry["types"][t]["clic"] = e["enveloppes"]["clic"]
        entry["types"][t]["corps"] = e["enveloppes"]["corps"]
    out["reglages"].append(entry)
out["t_ms"] = t_ms
out["source"] = src_env
out["source_bavure_db"] = m["source"]["bavure_db"]
json.dump(out, open(sys.argv[1], "w"))
print("OK ->", sys.argv[1])
