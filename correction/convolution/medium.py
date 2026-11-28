"""Zone 450-900 Hz « a plat » (trait de Rulio12 du 23/11/2026 sur la voie D, applique aux deux voies).
Cible : droite de +1 dB a 450 Hz a -2 dB a 850 Hz (cadre du graphique grenat : 1/6 oct., recale 200-500 Hz),
raccords 400-450 et 850-1000 Hz ; on ne touche ni au grave (< 400 Hz) ni au-dessus de 1 kHz.
Renfort limite a +4 dB (les creux etroits ne se comblent pas), coupe libre.
Depart : FIR *_grenat40 ; prevision = mesure verif_bouton_sans x (FIR / FIR de la mesure).

    python3 correction/convolution/medium.py   -> final/fir_{L,R}_{sanskick,kick}_grenat40m.raw, medium.png
"""
import os, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)
cible = np.interp(np.log(np.clip(f1, 450, 850)), np.log([450, 850]), [1.0, -2.0])
lg = lambda a, b: np.clip(np.log(f1 / a) / np.log(b / a), 0, 1)
w = (0.5 - 0.5 * np.cos(np.pi * lg(400, 450))) * (0.5 + 0.5 * np.cos(np.pi * lg(850, 1000)))


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def min_phase(G, n):
    c = np.fft.irfft(np.log(10 ** (G / 20)), N); ww = np.zeros(N); ww[0] = 1; ww[1:N // 2] = 2; ww[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * ww, N)), N)[:n]
    fade = n // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
res = {}
for ch in "LR":
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])   # meme cadre que grenat.png
    avant = smooth_db(db(base * fir(f"fir_{ch}_sanskick_grenat40.raw")), 1 / 6) - off
    delta = np.minimum(smooth_db(cible - avant, 1 / 6) * w, 4.0)
    for v in ("sanskick", "kick"):
        h0 = np.fromfile(os.path.join(D, "final", f"fir_{ch}_{v}_grenat40.raw"), "<f4").astype(float)
        G = db(np.fft.rfft(h0, N))
        G = G + delta
        h = min_phase(G, len(h0)); h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_grenat40m.raw"))
        if v == "sanskick":
            apres = smooth_db(db(base * np.fft.rfft(h, N)), 1 / 6) - off
            res[ch] = (avant, apres)
            sel = (f >= 450) & (f <= 850)
            gl = db(np.fft.rfft(h, N)); g0 = db(np.fft.rfft(h0, N))
            print(ch, "ecart au trait 450-850 Hz : avant", round(float(np.std((avant - cible)[sel])), 2), "apres", round(float(np.std((apres - cible)[sel])), 2),
                  "| sous 40 Hz vs avant max", round(float((gl - g0)[(f > 20) & (f < 40)].max()), 2), "| crete", round(float(gl[f < 20000].max()) - 20.5, 1), "dBFS")

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    a, b = res[ch]; m = (f >= 450) & (f <= 850)
    ax[j].plot(f[m], cible[m], color="#9b2335", lw=7, alpha=0.45, solid_capstyle="round", label="Ton trait 450-850 Hz")
    ax[j].plot(f[1:], a[1:], color="#8a8a85", lw=1.4, ls="--", label="Avant : trait grenat, rien sous 40 Hz")
    ax[j].plot(f[1:], b[1:], color="#2a78d6", lw=2.0, label="Avec la zone 450-900 Hz corrigee")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (FIR sans kick, 1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 5000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 40, 60, 100, 200, 300, 450, 600, 850, 1000, 2000, 5000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_xlabel("Hz")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[0].set_ylabel("dB")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=3, fontsize=10, frameon=False)
fig.suptitle("Zone 450-900 Hz mise a plat (version kick = meme correction)", fontsize=12)
fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(os.path.join(D, "medium.png"), dpi=130)
