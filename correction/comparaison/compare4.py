"""Les 4 corrections du grave archivees, et leur reponse attendue a la place d'ecoute.

Reponse attendue = mesure du 18/11 (resultats/ir/k0_origine, correction de l'epoque retiree)
x filtres de chaque correction. Tous les filtres sont comptes (Peaking, Lowshelf/Highshelf,
passe-haut Butterworth, FIR) sauf la loudness (depend du volume), le limiteur et les gains
constants (courbes recalees sur 200-1000 Hz). Moyenne 1/12 octave.

    python3 correction/comparaison/compare4.py   ->  correction/comparaison/compare4.png
"""
import json, os, sys
import numpy as np, yaml
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "mesure")); sys.path.insert(0, D)
from sweep_dsp import band_average_db
from filtres import chain, git_yml, FS

CORR = [  # (etiquette, config)
    ("1. A la main 19/07 (Lowshelf 100 Hz +5, coupes de modes)",
     yaml.safe_load(open(os.path.join(R, "correction/archive-pi/backup-juillet-2026/camilladspClaude.yml")))),
    ("2. EQ REW juillet (REW3, renforts Q eleve)",
     yaml.safe_load(open(os.path.join(R, "correction/test-juillet/camilladsp-qobuz-test-juillet.yml")))),
    ("3. Kick optimise + FIR 18/11 (tag reglage-2026-11-18-kick-fir)",
     git_yml("reglage-2026-11-18-kick-fir", "camilladsp/camilladsp-qobuz.yml")),
    ("4. Actuel : base 09/10 + creux renforces 22/11",
     yaml.safe_load(open(os.path.join(R, "camilladsp/camilladsp-qobuz.yml")))),
]

C = [round(20 * 2 ** (i / 24), 2) for i in range(0, 24 * 5) if 20 * 2 ** (i / 24) <= 600]
fc = np.array(C)

def bands(f, H):
    b = band_average_db(f, 20 * np.log10(np.abs(H) + 1e-12), C, frac_octave=1 / 12)
    return np.array([b[c] if b[c] is not None else np.nan for c in C])

z = np.load(os.path.join(R, "mesure/resultats/ir/k0_origine.npz"))
k0 = json.load(open(os.path.join(R, "mesure/resultats/ir/k0_origine.json")))["config"]
out = {"freq": C, "brut": {}, "eq": {}, "attendu": {}}
ref = (fc >= 200) & (fc <= 1000)
for ch, idx in (("L", 0), ("R", 1)):
    x = z[ch]; nf = 1 << (len(x) + FS - 1).bit_length(); f = np.fft.rfftfreq(nf, 1 / FS)
    raw = np.fft.rfft(x, nf) / chain(k0, idx, f)
    vb = bands(f, raw); off = np.nanmean(vb[(fc >= 200) & (fc <= 500)])
    out["brut"][ch] = (vb - off).tolist()
    for lab, cfg in CORR:
        he = chain(cfg, idx, f)
        ve = bands(f, he); out["eq"].setdefault(lab, {})[ch] = ve.tolist()  # gains constants deja retires
        va = bands(f, raw * he); out["attendu"].setdefault(lab, {})[ch] = (va - np.nanmean(va[(fc >= 200) & (fc <= 500)])).tolist()

sel = (fc >= 35) & (fc <= 300)
print("ecart-type 35-300 Hz (dB) :  G     D")
print(f"  sans correction           {np.nanstd(np.array(out['brut']['L'])[sel]):5.1f} {np.nanstd(np.array(out['brut']['R'])[sel]):5.1f}")
for lab, _ in CORR:
    a = out["attendu"][lab]
    print(f"  {lab[:26]:26s}{np.nanstd(np.array(a['L'])[sel]):5.1f} {np.nanstd(np.array(a['R'])[sel]):5.1f}")
json.dump(out, open(os.path.join(D, "compare4.json"), "w"), indent=1)

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
fig, ax = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    a = ax[0, j]
    a.plot(fc, out["brut"][ch], color="#8a8a85", lw=1.5, ls="--", label="Sans correction (mesure 18/11)")
    for k, (lab, _) in enumerate(CORR):
        a.plot(fc, out["attendu"][lab][ch], color=COL[k], lw=2, label=lab)
    a.set_title(f"{nom} : reponse attendue a la place d'ecoute"); a.set_ylim(-25, 20)
    b = ax[1, j]
    for k, (lab, _) in enumerate(CORR):
        b.plot(fc, out["eq"][lab][ch], color=COL[k], lw=2, label=lab)
    b.set_title(f"{nom} : courbe de l'EQ seule"); b.set_ylim(-20, 20)
for a in ax.flat:
    a.set_xscale("log"); a.set_xlim(20, 500); a.axhline(0, color="#bbb", lw=0.8)
    a.set_xticks([20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500]); a.set_xticklabels([20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500])
    a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); a.grid(True, which="major", color="#e6e6e3", lw=0.6); a.set_ylabel("dB")
    for s in ("top", "right"): a.spines[s].set_visible(False)
for a in ax[1]: a.set_xlabel("Hz")
h, l = ax[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, fontsize=9, frameon=False)
fig.suptitle("Les 4 corrections du grave : reponse attendue (mesure du 18/11 + EQ, 1/12 oct., recale 200-500 Hz ; EQ sans preamp ni loudness)", fontsize=12)
fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(os.path.join(D, "compare4.png"), dpi=130)
