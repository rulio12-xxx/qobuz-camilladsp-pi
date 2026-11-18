#!/home/rulio12/audio-power/venv/bin/python3
"""Lit ou change en direct des parametres de filtres CamillaDSP (sans rechargement).

    ./regle.py delay_L.delay                      # lit
    ./regle.py delay_L.delay=0 click_boost.gain=4 # change
    ./regle.py --fichier iterations/.../k1.json   # {"filtre.param": valeur, ...}

Les changements sont perdus au prochain changement de source ou rechargement de
la config : reporter les valeurs retenues dans les YAML de camilladsp/.
"""
import json
import sys

from camilladsp import CamillaClient

c = CamillaClient("127.0.0.1", 1234)
c.connect()
args = sys.argv[1:]
if args and args[0] == "--fichier":
    args = [f"{k}={v}" for k, v in json.load(open(args[1])).items()]
for a in args:
    if "=" in a:
        k, v = a.split("=", 1)
        f, p = k.split(".", 1)
        val = {"true": True, "false": False}.get(v.lower())
        if val is None:
            try:
                val = float(v)
            except ValueError:
                val = v          # texte, ex. unit=samples
        c.config.set_value(f"/filters/{f}/parameters/{p}", val)
    k = a.split("=", 1)[0]
    f, p = k.split(".", 1)
    print(f"{k} = {c.config.get_value(f'/filters/{f}/parameters/{p}')}")
