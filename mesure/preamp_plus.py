"""Ajoute N dB au preamp de chaque configuration (texte, mise en forme gardee).
    python3 preamp_plus.py <dB> <suffixe_sauvegarde>"""
import os, re, shutil, subprocess, sys
CFG = "/home/rulio12/camilladsp/configs"
FICHIERS = ["camilladsp-qobuz.yml", "camilladsp-bluetooth.yml", "camilladsp-fichiers.yml",
            "camilladsp-cd.yml", "camilladsp-vinyle.yml", "camilladsp.yml",
            "camilladsp-qobuz.yml.avant-tube", "camilladsp-bluetooth.yml.avant-tube",
            "camilladsp-fichiers.yml.avant-tube"]
d, suf = float(sys.argv[1]), sys.argv[2]
for fn in FICHIERS:
    p = os.path.join(CFG, fn)
    t = open(p).read()
    m = re.search(r"(^  preamp:\s*\n(?:    .*\n)*?\s*gain:\s*)(-?[0-9.]+)", t, flags=re.M)
    old = float(m.group(2)); new = round(old + d, 2)
    bak = p + "." + suf
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    open(p, "w").write(t[:m.start(2)] + f"{new:g}" + t[m.end(2):])
    ok = True
    if fn.endswith(".yml"):
        r = subprocess.run(["camilladsp", "--check", p], capture_output=True, text=True)
        ok = "Config is valid" in r.stdout + r.stderr
        if not ok:
            shutil.copy2(bak, p)
    print(f"{fn:40} preamp {old:g} -> {new:g} dB" + ("" if ok else "  !!! refuse, remis"))
