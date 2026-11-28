#!/usr/bin/env python3
"""Tableau Markdown des filtres actifs d'une config CamillaDSP (lecture seule).

    python3 correction/tableau_filtres.py camilladsp/camilladsp-qobuz.yml

Liste, etape par etape du pipeline, chaque filtre avec ses parametres.
Ne modifie rien et ne parle pas a CamillaDSP : lit seulement le YAML.
"""
import sys

import yaml

cfg = yaml.safe_load(open(sys.argv[1] if len(sys.argv) > 1 else "camilladsp/camilladsp-qobuz.yml"))
filtres = cfg.get("filters", {})
voies = {(0,): "G", (1,): "D", (0, 1): "G+D"}


def decrit(nom):
    f = filtres[nom]
    p = f.get("parameters", {})
    t = f["type"]
    if t == "Biquad":
        q = p.get("q", p.get("slope", ""))
        return f"{p.get('type')} | {p.get('freq', '')} | {p.get('gain', '')} | {q}"
    if t == "Gain":
        return f"Gain | | {p.get('gain')} |"
    if t == "Delay":
        return f"Delay | | {p.get('delay')} {p.get('unit', 'ms')} |"
    if t == "Conv":
        return f"FIR ({p.get('filename', '')}) | | |"
    return f"{t} | | |"


print("| Etape | Voie | Filtre | Type | Freq (Hz) | Gain (dB) | Q |")
print("|---|---|---|---|---|---|---|")
for i, st in enumerate(cfg["pipeline"], 1):
    if st["type"] == "Processor":
        print(f"| {i} | G+D | {st['name']} | processeur | | | |")
        continue
    v = voies.get(tuple(st.get("channels", [])), str(st.get("channels")))
    for n in st["names"]:
        print(f"| {i} | {v} | {n} | {decrit(n)} |")
