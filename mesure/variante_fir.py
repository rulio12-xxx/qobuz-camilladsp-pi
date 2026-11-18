#!/home/rulio12/audio-power/venv/bin/python3
"""FIR de correction de phase du grave : ajout, retrait, contournement en direct.

    ./variante_fir.py on          # ajoute l'etape phase_grave (recharge, courte coupure)
    ./variante_fir.py off         # la retire (recharge)
    ./variante_fir.py contourne   # la contourne en direct, sans coupure
    ./variante_fir.py actif       # la remet en service en direct
    ./variante_fir.py check       # ecrit /tmp/fir-test.yml et le fait valider
    ./variante_fir.py etat

Un seul FIR, commun aux deux voies (fir.py --commun), dans sa propre etape de la
chaine, juste avant le limiteur : on peut donc le contourner sans recharger.
"""
import copy
import subprocess
import sys
import time

import yaml
from camilladsp import CamillaClient

FIR_DIR = "/home/rulio12/camilladsp/fir"
NAME = "phase_grave"
FILE = f"{FIR_DIR}/phase_L.raw"

c = CamillaClient("127.0.0.1", 1234)
c.connect()
cfg = c.config.active()
cmd = sys.argv[1]


def step_index(cfg):
    for i, st in enumerate(cfg["pipeline"]):
        if st.get("type") == "Filter" and st.get("names") == [NAME]:
            return i
    return None


def with_fir(cfg):
    new = copy.deepcopy(cfg)
    new["filters"][NAME] = {"type": "Conv", "description": "correction de phase du grave (mesure/fir.py)",
                            "parameters": {"type": "Raw", "filename": FILE, "format": "F32_LE"}}
    if step_index(new) is None:
        lim = next(i for i, st in enumerate(new["pipeline"]) if st.get("names") == ["limiter"])
        new["pipeline"].insert(lim, {"type": "Filter", "channels": [0, 1], "names": [NAME], "bypassed": False})
    return new


def without_fir(cfg):
    new = copy.deepcopy(cfg)
    new["filters"].pop(NAME, None)
    new["pipeline"] = [st for st in new["pipeline"] if st.get("names") != [NAME]]
    return new


def clean(d):
    if isinstance(d, dict):
        return {k: clean(v) for k, v in d.items() if v is not None}
    if isinstance(d, list):
        return [clean(v) for v in d]
    return d


def etat(cfg):
    i = step_index(cfg)
    if i is None:
        return "FIR absent"
    return "FIR contourne" if cfg["pipeline"][i].get("bypassed") else "FIR en service"


if cmd == "etat":
    print(etat(cfg))
elif cmd == "check":
    yaml.safe_dump(clean(with_fir(cfg)), open("/tmp/fir-test.yml", "w"), sort_keys=False)
    r = subprocess.run(["camilladsp", "--check", "/tmp/fir-test.yml"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[0])
elif cmd in ("contourne", "actif"):
    i = step_index(cfg)
    if i is None:
        sys.exit("FIR absent de la configuration active")
    c.config.set_value(f"/pipeline/{i}/bypassed", cmd == "contourne")
    time.sleep(0.3)
    print(etat(c.config.active()))
elif cmd in ("on", "off"):
    c.config.set_active(with_fir(cfg) if cmd == "on" else without_fir(cfg))
    time.sleep(1.0)
    print(etat(c.config.active()))
