"""Creux et bosses du grave sur toutes les mesures du depot (reponses impulsionnelles
resultats/ir/*.npz et campagnes resultats/2026-*/), correction retiree : reponse brute
1/12 octave, ref 500-2500 Hz. Affiche mediane, min, max et % de mesures sous -5 dB.

    python3 correction/test-creux/creux.py
"""
import json, glob, os, sys
import numpy as np
M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mesure")
sys.path.insert(0, M)
from sweep_dsp import band_average_db
from ir2 import chain_h, FS
C = [round(20 * 2 ** (i / 12), 2) for i in range(0, 120) if 20 * 2 ** (i / 12) <= 20000]
fc = np.array(C)
ref = (fc >= 500) & (fc <= 2500)

def eq_db(cfg, idx, f):
    h = chain_h(cfg, idx, np.asarray(f, float))
    # retirer gain constant (preamp)
    return 20 * np.log10(np.abs(h))

raws = {"L": [], "R": []}; labels = []
for p in sorted(glob.glob(M + "/resultats/ir/*.npz")):
    lab = os.path.basename(p)[:-4]
    z = np.load(p); meta = json.load(open(p[:-4] + ".json")); cfg = meta["config"]
    for ch, idx in (("L", 0), ("R", 1)):
        x = z[ch]; nf = 1 << (len(x) - 1).bit_length()
        f = np.fft.rfftfreq(nf, 1 / FS)
        H = np.fft.rfft(x, nf) / chain_h(cfg, idx, f)
        b = band_average_db(f, 20 * np.log10(np.abs(H) + 1e-12), C, frac_octave=1 / 12)
        v = np.array([b[c] if b[c] is not None else np.nan for c in C])
        raws[ch].append(v - np.nanmean(v[ref]))
    labels.append("ir:" + lab)
for d in sorted(glob.glob(M + "/resultats/2026-*/")):
    nv = json.load(open(d + "niveaux.json"))["niveaux"]
    cfg = json.load(open(d + "config_active.json"))["config"]
    for lv, chans in nv.items():
        for ch, idx in (("L", 0), ("R", 1)):
            b = chans[ch].get("bands_12")
            if not b: continue
            v = np.array([b.get(str(c), b.get(c, np.nan)) if isinstance(b, dict) else np.nan for c in C], float) if isinstance(b, dict) else np.array(b, float)
            v = v - eq_db(cfg, idx, fc)
            raws[ch].append(v - np.nanmean(v[ref]))
        labels.append(os.path.basename(d.rstrip('/')) + "@" + lv)
print("mesures:", len(raws["L"]))
sel = (fc >= 30) & (fc <= 320)
for ch in "LR":
    A = np.array(raws[ch])
    print(f"\n== {ch} : freq | mediane | min | max | % mesures < -5 dB")
    for i in np.where(sel)[0]:
        col = A[:, i]
        print(f"{fc[i]:6.1f} {np.nanmedian(col):6.1f} {np.nanmin(col):6.1f} {np.nanmax(col):6.1f} {100*np.mean(col < -5):4.0f}%")
pass
