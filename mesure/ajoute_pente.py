"""Ajoute une pente douce dans l'aigu (filtre aigu_pente, commun G/D) aux YAML.

    python3 ajoute_pente.py <gain_dB> <suffixe_sauvegarde>

Highshelf 2500 Hz, Q 0,5 (transition tres progressive), dans sa propre etape
[0, 1] juste avant le limiteur ; le gain se change ensuite en direct :
    ./regle.py aigu_pente.gain=-2
Fichiers de base des lampes (.avant-tube) compris ; relancer ensuite
apply_tube.sh <niveau> pour regenerer les configurations actives.
"""
import os
import re
import shutil
import subprocess
import sys

CFG_DIR = "/home/rulio12/camilladsp/configs"
CIBLES = ["camilladsp-qobuz.yml.avant-tube", "camilladsp-bluetooth.yml.avant-tube",
          "camilladsp-fichiers.yml.avant-tube", "camilladsp-cd.yml", "camilladsp-vinyle.yml",
          "camilladsp-qobuz.yml", "camilladsp-bluetooth.yml", "camilladsp-fichiers.yml", "camilladsp.yml"]
gain = float(sys.argv[1])
suffix = sys.argv[2]
FILTRE = f"""  aigu_pente:
    type: Biquad
    description: pente douce dans l'aigu (demande du 20/11/2026)
    parameters:
      type: Highshelf
      freq: 2500
      gain: {gain:g}
      q: 0.5
"""

for fname in CIBLES:
    path = os.path.join(CFG_DIR, fname)
    if not os.path.exists(path):
        continue
    text = open(path).read()
    if "aigu_pente" in text:
        print(f"{fname:40} deja present")
        continue
    new, n1 = re.subn(r"^filters:\s*\n", lambda m: m.group(0) + FILTRE, text, count=1, flags=re.M)
    m = re.search(r"^(\s*)- type: Filter\s*\n\s*channels: \[0, 1\]\s*\n\s*names:\s*\n\s*- limiter\s*$", new, flags=re.M)
    if n1 != 1 or not m:
        print(f"{fname:40} structure inattendue, rien change")
        continue
    ind = m.group(1)
    step = f"{ind}- type: Filter\n{ind}  channels: [0, 1]\n{ind}  names:\n{ind}    - aigu_pente\n"
    new = new[:m.start()] + step + new[m.start():]
    bak = f"{path}.{suffix}"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    open(path, "w").write(new)
    ok = True
    if fname.endswith(".yml"):
        r = subprocess.run(["camilladsp", "--check", path], capture_output=True, text=True)
        ok = "Config is valid" in r.stdout + r.stderr
        if not ok:
            shutil.copy2(bak, path)
    print(f"{fname:40} {'ajoute' if ok else '!!! refuse, remis'}")
