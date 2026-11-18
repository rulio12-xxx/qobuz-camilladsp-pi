#!/home/rulio12/audio-power/venv/bin/python3
"""Remet en direct les reglages de filtres d'une iteration (sa copie config_active.json).

    ./restaure.py resultats/<campagne>/config_active.json

Applique gain/freq/q de tous les filtres Peaking et les parametres des Delay,
sans recharger la config (pas de coupure). Le loudness et le volume ne sont pas
touches.
"""
import json
import sys

from camilladsp import CamillaClient

cfg = json.load(open(sys.argv[1]))["config"]
c = CamillaClient("127.0.0.1", 1234)
c.connect()
live = c.config.active()["filters"]
n = 0
for name, flt in cfg["filters"].items():
    if name in ("loud_bass", "loud_treble") or name not in live:
        continue
    p = flt["parameters"]
    if flt["type"] == "Biquad" and p.get("type") == "Peaking":
        keys = ("freq", "gain", "q")
    elif flt["type"] == "Delay":
        keys = ("unit", "subsample", "delay")
    else:
        continue
    for k in keys:
        if live[name]["parameters"].get(k) != p[k]:
            c.config.set_value(f"/filters/{name}/parameters/{k}", p[k])
            n += 1
print(f"{n} parametre(s) remis comme dans {sys.argv[1]}")
