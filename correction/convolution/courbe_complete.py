"""Courbe complete 20 Hz - 20 kHz de la version active (23/11/2026) : FIR sans kick et kick *_l456,
avec la cible assemblee (trait grenat, droites 380-560, 450-850 Hz, 850 Hz-5 kHz, 0 dB 5-9 kHz) et,
pour reference, la premiere version par convolution (bosse +13 dB). Calcule sur la mesure verif_bouton_sans,
1/6 oct., cadre des graphiques grenat.

    python3 correction/convolution/courbe_complete.py   -> courbe_complete.png
"""
import os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


PTS = [(40, 2.0), (45, 3.5), (50, 4.3), (60, 4.5), (70, 4.6), (80, 4.7), (90, 4.0), (100, 2.5), (110, 1.3), (130, 0.0),
       (150, -1.0), (180, -1.8), (200, -1.6), (250, -1.5), (300, -1.7), (380, -2.0), (560, 0.0), (850, -2.0), (5000, 0.0), (9000, 0.0)]
cf = np.array([p[0] for p in PTS], float); m = (f >= 40) & (f <= 9000)
cible = np.interp(np.log(f1), np.log(cf), [p[1] for p in PTS])
# 450-850 : droite +1 -> -2 (la jonction 380-560 l'emporte en dessous de 560)
seg = (f >= 560) & (f <= 850); cible[seg] = np.interp(np.log(f[seg]), np.log([450, 850]), [1.0, -2.0])
z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])
    c = lambda n: smooth_db(db(base * fir(n)), 1 / 6) - off
    ax[j].plot(f[m], cible[m], color="#9b2335", lw=7, alpha=0.35, solid_capstyle="round", label="Cible assemblee")
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_avant38.raw")[1:], color="#b9b8b2", lw=1.2, ls="--", label="Premiere convolution (bosse +13 dB, 22/11)")
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_l456.raw")[1:], color="#2a78d6", lw=2.0, label="Actif : sans kick")
    ax[j].plot(f[1:], c(f"fir_{ch}_kick_l456.raw")[1:], color="#eb6834", lw=1.3, label="Actif : kick (+ renfort 2-10 kHz)")
    ax[j].axvline(40, color="#9b2335", lw=0.8, ls=":")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 20000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 60, 100, 200, 300, 500, 1000, 2000, 5000, 10000, 20000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_ylabel("dB")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[1].set_xlabel("Hz")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=4, fontsize=10, frameon=False)
fig.suptitle("Courbe complete de la version active (23/11, 22 h 35)", fontsize=12)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(D, "courbe_complete.png"), dpi=130)
