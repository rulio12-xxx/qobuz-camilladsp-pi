#!/home/rulio12/audio-power/venv/bin/python3
"""Active / retire en direct le FIR de correction de phase du grave.

    ./variante_fir.py on       # ajoute phase_L / phase_R (fichiers ~/camilladsp/fir/*.raw)
    ./variante_fir.py off      # les retire
    ./variante_fir.py check    # ecrit /tmp/fir-test.yml et le fait valider, sans rien activer
    ./variante_fir.py etat

Part de la configuration active (avec les reglages faits en direct), ajoute les
deux filtres Conv en fin de chaine de chaque voie et recharge cette configuration
(courte coupure). Perdu a la prochaine veille ou au prochain changement de source,
tant que le FIR n'est pas ecrit dans les YAML.
"""
import copy
import subprocess
import sys

import yaml
from camilladsp import CamillaClient

FIR_DIR = "/home/rulio12/camilladsp/fir"
NAMES = {0: "phase_L", 1: "phase_R"}

c = CamillaClient("127.0.0.1", 1234)
c.connect()
cfg = c.config.active()
cmd = sys.argv[1]


def has_fir(cfg):
    return any(n in cfg["filters"] for n in NAMES.values())


def with_fir(cfg):
    new = copy.deepcopy(cfg)
    for ch, name in NAMES.items():
        new["filters"][name] = {"type": "Conv", "description": "correction de phase du grave (mesure/fir.py)",
                                "parameters": {"type": "Raw", "filename": f"{FIR_DIR}/{name}.raw",
                                               "format": "F32_LE", "skip_bytes_lines": 0, "read_bytes_lines": 0}}
        for step in new["pipeline"]:
            if step.get("type") == "Filter" and step.get("channels") == [ch] and name not in step["names"]:
                step["names"].append(name)
                break
    return new


def without_fir(cfg):
    new = copy.deepcopy(cfg)
    for name in NAMES.values():
        new["filters"].pop(name, None)
    for step in new["pipeline"]:
        if step.get("type") == "Filter":
            step["names"] = [n for n in step["names"] if n not in NAMES.values()]
    return new


def clean(d):
    """retire les cles a None (refusees par certaines versions de --check)."""
    if isinstance(d, dict):
        return {k: clean(v) for k, v in d.items() if v is not None}
    if isinstance(d, list):
        return [clean(v) for v in d]
    return d


if cmd == "etat":
    print("FIR actif" if has_fir(cfg) else "FIR absent")
elif cmd == "check":
    yaml.safe_dump(clean(with_fir(without_fir(cfg))), open("/tmp/fir-test.yml", "w"), sort_keys=False)
    r = subprocess.run(["camilladsp", "--check", "/tmp/fir-test.yml"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-400:])
elif cmd in ("on", "off"):
    new = with_fir(without_fir(cfg)) if cmd == "on" else without_fir(cfg)
    c.config.set_active(new)
    print("FIR active" if cmd == "on" else "FIR retire", "->", "actif" if has_fir(c.config.active()) else "absent")
