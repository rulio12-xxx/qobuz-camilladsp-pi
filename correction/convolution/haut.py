"""Suite de la mise a plat (Rulio12, 23/11/2026) : de 850 Hz a 5 kHz, courbe tres lissee, memes deux voies.
Cible : droite de -2 dB a 850 Hz a 0 dB a 5 kHz (0 = moyenne G/D a 5 kHz ; cadre des graphiques grenat),
raccord 5-6,5 kHz ; rien ne change sous 850 Hz ni au-dessus de 6,5 kHz. Correction lissee au 1/3 d'octave,
renfort limite a +4 dB. Version kick = nouveau sans kick x clic 4,5 kHz +1,5 dB Q1 (renfort 2-10 kHz garde).
Depart : FIR *_grenat40m.

    python3 correction/convolution/haut.py   -> final/fir_{L,R}_{sanskick,kick}_plat5k.raw, haut.png
"""
import os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)
cible = np.interp(np.log(np.clip(f1, 850, 5000)), np.log([850, 5000]), [-2.0, 0.0])
lg = lambda a, b: np.clip(np.log(f1 / a) / np.log(b / a), 0, 1)
w = (0.5 - 0.5 * np.cos(np.pi * lg(800, 850))) * (0.5 + 0.5 * np.cos(np.pi * lg(5000, 6500)))


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def min_phase(G, n):
    c = np.fft.irfft(np.log(10 ** (G / 20)), N); ww = np.zeros(N); ww[0] = 1; ww[1:N // 2] = 2; ww[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * ww, N)), N)[:n]
    fade = n // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


def clic(h):
    A = 10 ** (1.5 / 40); w0 = 2 * np.pi * 4500 / FS; al = np.sin(w0) / 2; c = np.cos(w0)
    b = np.array([1 + al * A, -2 * c, 1 - al * A]); a = np.array([1 + al / A, -2 * c, 1 - al / A]); b, a = b / a[0], a / a[0]
    y = np.zeros_like(h); x1 = x2 = y1 = y2 = 0.0
    for n, xn in enumerate(h):
        yn = b[0] * xn + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1, y2, y1 = x1, xn, y1, yn; y[n] = yn
    return y


z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
res = {}
for ch in "LR":
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])
    avant = smooth_db(db(base * fir(f"fir_{ch}_sanskick_grenat40m.raw")), 1 / 6) - off
    delta = np.minimum(smooth_db(cible - smooth_db(db(base * fir(f"fir_{ch}_sanskick_grenat40m.raw")), 1 / 3) + off, 1 / 3) * w, 4.0)
    h0 = np.fromfile(os.path.join(D, "final", f"fir_{ch}_sanskick_grenat40m.raw"), "<f4").astype(float)
    h = min_phase(db(np.fft.rfft(h0, N)) + delta, len(h0))
    h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_sanskick_plat5k.raw"))
    k = clic(h); fade = len(k) // 8; k[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    k.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_kick_plat5k.raw"))
    apres = smooth_db(db(base * np.fft.rfft(h, N)), 1 / 6) - off
    kick = smooth_db(db(base * np.fft.rfft(k, N)), 1 / 6) - off
    res[ch] = (avant, apres, kick)
    sel = (f >= 850) & (f <= 5000)
    a3 = smooth_db(db(base * np.fft.rfft(h, N)), 1 / 3) - off; b3 = smooth_db(db(base * np.fft.rfft(h0, N)), 1 / 3) - off
    print(ch, "ecart a la droite 850-5k (1/3 oct.) : avant", round(float(np.std((b3 - cible)[sel])), 2), "apres", round(float(np.std((a3 - cible)[sel])), 2),
          "| sous 800 Hz max", round(float(np.abs(db(np.fft.rfft(h, N)) - db(np.fft.rfft(h0, N)))[(f > 20) & (f < 780)].max()), 2),
          "| crete", round(float(db(np.fft.rfft(k, N))[f < 20000].max()) - 20.5, 1), "dBFS")

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    a, b, k = res[ch]; m = (f >= 850) & (f <= 5000)
    ax[j].plot(f[m], cible[m], color="#9b2335", lw=7, alpha=0.45, solid_capstyle="round", label="Cible lissee 850 Hz - 5 kHz")
    ax[j].plot(f[1:], a[1:], color="#8a8a85", lw=1.3, ls="--", label="Avant (zone 450-900 a plat)")
    ax[j].plot(f[1:], b[1:], color="#2a78d6", lw=2.0, label="Sans kick, plat jusqu'a 5 kHz")
    ax[j].plot(f[1:], k[1:], color="#eb6834", lw=1.4, label="Kick (+ renfort 2-10 kHz)")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 20000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 40, 60, 100, 200, 450, 850, 2000, 5000, 10000, 20000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_xlabel("Hz")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[0].set_ylabel("dB")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=4, fontsize=10, frameon=False)
fig.suptitle("Mise a plat prolongee jusqu'a 5 kHz (courbe lissee), renfort 2-10 kHz garde sur la version kick", fontsize=12)
fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(os.path.join(D, "haut.png"), dpi=130)
