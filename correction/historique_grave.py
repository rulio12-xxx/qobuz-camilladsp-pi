#!/usr/bin/env python3
"""Historique des filtres du grave (Biquad <= 200 Hz + preamp) dans l'historique git.

    python3 correction/historique_grave.py [branche] [fichier_yaml] [freq_max]

Lecture seule : parcourt les commits qui ont modifie le YAML (par defaut
origin/main, camilladsp/camilladsp-qobuz.yml, 200 Hz) et affiche, a chaque
commit, les filtres du grave qui ont change (avant -> apres).
Dans un clone superficiel, recuperer d'abord l'historique :
git fetch --depth=200 origin main
"""
import subprocess
import sys

import yaml

REF = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
YML = sys.argv[2] if len(sys.argv) > 2 else "camilladsp/camilladsp-qobuz.yml"
FMAX = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def grave(cfg):
    out = {}
    for nom, f in (cfg.get("filters") or {}).items():
        p = f.get("parameters", {})
        if f.get("type") == "Biquad" and isinstance(p.get("freq"), (int, float)) and p["freq"] <= FMAX:
            out[nom] = (p.get("type"), p.get("freq"), p.get("gain"), p.get("q"))
    out["preamp"] = (cfg.get("filters", {}).get("preamp", {}).get("parameters", {}).get("gain"),)
    return out


prec = None
for ligne in sh("git", "log", "--reverse", "--format=%h|%ad|%s", "--date=short", REF, "--", YML).splitlines():
    h, d, s = ligne.split("|", 2)
    try:
        cur = grave(yaml.safe_load(sh("git", "show", f"{h}:{YML}")))
    except Exception as e:  # YAML illisible a ce commit
        print(f"{h} : illisible ({e})")
        continue
    if cur == prec:
        continue
    print(f"\n## {h} {d} {s}")
    for k in sorted(cur):
        if prec is None or prec.get(k) != cur[k]:
            print(f"  {k}: {prec.get(k) if prec else '-'} -> {cur[k]}")
    for k in sorted(prec or {}):
        if k not in cur:
            print(f"  {k}: supprime")
    prec = cur
