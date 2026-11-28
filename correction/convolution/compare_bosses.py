"""Reponse attendue a la place d'ecoute des FIR sans kick avec la bosse du grave a +13, +10 et +7 dB (23/11/2026).
Base : mesure verif_bouton_sans (22/11, FIR sans kick d'origine = final/*_sanskick_avant38.raw),
x (FIR teste / FIR d'origine) : exact pour une chaine lineaire. Lissage 1/6 oct., recale 200-500 Hz.

    python3 correction/convolution/compare_bosses.py   -> compare_bosses.png
"""
import os, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "correction", "comparaison")); sys.path.insert(0, D)
from cible import cible_db
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
V = [("+13 dB", "sanskick", 11.0, 58.0, "#8a8a85"), ("+10 dB", "sanskick_b10", 7.25, 58.0, "#eb6834"), ("+7 dB", "sanskick_b7", 4.0, 58.0, "#2a78d6")]
TITRE = "Bosse du grave a +13, +10 et +7 dB"; OUT = "compare_bosses.png"
if "--freq" in sys.argv:   # bosse +7 dB a 56, 66 et 76 Hz
    V = [("+7 dB a 56 Hz", "sanskick_b7", 4.0, 58.0, "#8a8a85"), ("+7 dB a 66 Hz", "sanskick_b7f66", 4.5, 70.0, "#eb6834"), ("+7 dB a 76 Hz (actif)", "sanskick_b7f76", 5.0, 82.0, "#2a78d6")]
    TITRE = "Bosse du grave +7 dB a 56, 66 et 76 Hz"; OUT = "compare_bosses_freq.png"
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    for lab, suf, b, fb, col in V:
        s = smooth_db(db(base * fir(f"fir_{ch}_{suf}.raw")), 1 / 6); s -= np.mean(s[REF])
        ax[j].plot(f[1:], s[1:], color=col, lw=2.0, label=f"Bosse {lab}")
        c = cible_db(f, b, fb); ax[j].plot(f[1:], c[1:], color=col, lw=1.2, ls=":", label=f"cible {lab}")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (FIR sans kick, 1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 20000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000, 2000, 5000, 10000, 20000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t], fontsize=8)
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_xlabel("Hz")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
[a.set_xlim(20, 1000) for a in ax] if "--freq" in sys.argv else None
ax[0].set_ylabel("dB")
h, l = ax[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=6, fontsize=9.5, frameon=False)
fig.suptitle(TITRE + " (version kick = meme grave, +0,8 dB entre 2 et 10 kHz)", fontsize=12)
fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(os.path.join(D, OUT), dpi=130)
