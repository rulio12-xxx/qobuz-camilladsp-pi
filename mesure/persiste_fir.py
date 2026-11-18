"""Ajoute l'etape FIR phase_grave dans les YAML CamillaDSP (texte, mise en forme gardee).

    python3 persiste_fir.py <suffixe_sauvegarde> [--essai]

- filtre phase_grave (Conv, Raw F32_LE, ~/camilladsp/fir/phase_L.raw) en tete de filters:
- etape [0, 1] phase_grave juste avant l'etape du limiteur
Ne fait rien si phase_grave est deja present. camilladsp --check apres ecriture ;
fichier remis si refuse.
"""
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
FILTRE = """  phase_grave:
    type: Conv
    description: correction de phase du grave (mesure/fir.py, 18/11/2026)
    parameters:
      type: Raw
      filename: /home/rulio12/camilladsp/fir/phase_L.raw
      format: F32_LE
"""
suffix = sys.argv[1]
essai = "--essai" in sys.argv

for fname in CIBLES:
    path = os.path.join(CFG_DIR, fname)
    if not os.path.exists(path):
        continue
    text = open(path).read()
    if "phase_grave" in text:
        print(f"== {fname} : deja present")
        continue
    new, n1 = re.subn(r"^filters:\s*\n", lambda m: m.group(0) + FILTRE, text, count=1, flags=re.M)
    m = re.search(r"^(\s*)- type: Filter\s*\n\s*channels: \[0, 1\]\s*\n\s*names:\s*\n\s*- limiter\s*$", new, flags=re.M)
    if n1 != 1 or not m:
        print(f"== {fname} : structure inattendue, rien change")
        continue
    ind = m.group(1)
    step = f"{ind}- type: Filter\n{ind}  channels: [0, 1]\n{ind}  names:\n{ind}    - phase_grave\n"
    new = new[:m.start()] + step + new[m.start():]
    print(f"== {fname} : filtre + etape ajoutes")
    if essai:
        continue
    bak = f"{path}.{suffix}"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    open(path, "w").write(new)
    if fname.endswith(".yml"):
        r = subprocess.run(["camilladsp", "--check", path], capture_output=True, text=True)
        if "Config is valid" not in (r.stdout + r.stderr):
            shutil.copy2(bak, path)
            print("   !!! refuse par camilladsp --check, fichier remis :", (r.stdout + r.stderr)[-300:])
