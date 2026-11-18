"""Reporte des reglages de filtres dans les configurations CamillaDSP (YAML).

    python3 persiste.py <config_active.json | ir/<etiquette>.json> <suffixe_sauvegarde> [--essai]

Prend les filtres Peaking (freq, gain, q) et Delay (delay, unit, subsample) de la
configuration donnee et les ecrit dans chaque YAML qui contient un filtre du meme
nom : seules les valeurs changent (mise en forme et commentaires gardes).
Avant d'ecrire : copie <fichier>.<suffixe>. Apres : camilladsp --check ; si un
fichier est refuse, il est remis tel qu'il etait.
Le loudness (loud_bass/loud_treble) n'est jamais touche.
--essai : affiche les changements sans rien ecrire.
"""
import json
import os
import re
import shutil
import subprocess
import sys

CFG_DIR = "/home/rulio12/camilladsp/configs"
CIBLES = ["camilladsp-qobuz.yml", "camilladsp-bluetooth.yml", "camilladsp-fichiers.yml",
          "camilladsp-cd.yml", "camilladsp-vinyle.yml", "camilladsp.yml",
          "camilladsp-qobuz.yml.avant-tube", "camilladsp-bluetooth.yml.avant-tube",
          "camilladsp-fichiers.yml.avant-tube"]
SKIP = {"loud_bass", "loud_treble"}

src = json.load(open(sys.argv[1]))["config"]["filters"]
suffix = sys.argv[2]
essai = "--essai" in sys.argv


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        v = float(v)
        return str(int(v)) if v.is_integer() else f"{v:.4g}" if abs(v) >= 1000 else f"{round(v, 3)}"
    return str(v)


def edit(text, name, params):
    """remplace les valeurs de params dans le bloc du filtre `name`."""
    lines = text.split("\n")
    head = re.compile(rf"^(\s*){re.escape(name)}:\s*$")
    i0 = next((i for i, l in enumerate(lines) if head.match(l)), None)
    if i0 is None:
        return text, []
    ind = len(head.match(lines[i0]).group(1))
    changes = []
    i = i0 + 1
    while i < len(lines):
        l = lines[i]
        if l.strip() and (len(l) - len(l.lstrip())) <= ind:
            break                      # fin du bloc du filtre
        m = re.match(r"^(\s*)(freq|gain|q|delay|unit|subsample):\s*([^#\n]*?)(\s*#.*)?$", l)
        if m and m.group(2) in params:
            new = fmt(params[m.group(2)])
            old = m.group(3).strip()
            if old != new:
                try:
                    same = float(old) == float(new)
                except ValueError:
                    same = old.lower() == new.lower()
                if not same:
                    lines[i] = f"{m.group(1)}{m.group(2)}: {new}{m.group(4) or ''}"
                    changes.append(f"{name}.{m.group(2)} {old} -> {new}")
        i += 1
    return "\n".join(lines), changes


total = 0
for fname in CIBLES:
    path = os.path.join(CFG_DIR, fname)
    if not os.path.exists(path):
        continue
    text = open(path).read()
    allc = []
    for name, flt in src.items():
        if name in SKIP:
            continue
        p = flt["parameters"]
        if flt["type"] == "Biquad" and p.get("type") == "Peaking":
            params = {k: p[k] for k in ("freq", "gain", "q")}
        elif flt["type"] == "Delay":
            params = {k: p[k] for k in ("delay", "unit", "subsample") if k in p}
        else:
            continue
        text, c = edit(text, name, params)
        allc += c
    print(f"== {fname} : {len(allc)} changement(s)")
    for c in allc:
        print("   ", c)
    if essai or not allc:
        continue
    bak = f"{path}.{suffix}"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    open(path, "w").write(text)
    if fname.endswith(".yml"):
        r = subprocess.run(["camilladsp", "--check", path], capture_output=True, text=True)
        if "Config is valid" not in (r.stdout + r.stderr):
            shutil.copy2(bak, path)
            print("   !!! refuse par camilladsp --check, fichier remis :", (r.stdout + r.stderr)[-300:])
            continue
    total += len(allc)
print(f"Total : {total} valeur(s) ecrite(s)" + (" (essai, rien ecrit)" if essai else ""))
