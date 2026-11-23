"""Cible « trait grenat » dessinee par Rulio12 le 23/11/2026 sur compare_bosses_freq.png (voie G),
appliquee aux deux voies, par convolution, sans mesure.

Points lus sur le dessin (dB, cadre du graphique : 1/6 oct., recale 200-500 Hz) ; rien n'est
renforce sous 38 Hz (rampe 38-44 Hz), au-dessus de 400 Hz rien ne change (raccord 400-480 Hz).
Depart : FIR actifs *_b7f76 ; prevision = mesure verif_bouton_sans x (FIR / FIR de la mesure).
Delta = cible - prevision (lisse 1/6 oct.), applique aux FIR sans kick et kick (meme delta).

    python3 correction/convolution/grenat.py   -> final/fir_{L,R}_{sanskick,kick}_grenat.raw, grenat.png
    python3 correction/convolution/grenat.py --sous40   -> *_grenat40.raw, grenat40.png : aucun renfort sous 40 Hz
"""
import os, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500)
PTS = [(38, 0.0), (40, 2.0), (45, 3.5), (50, 4.3), (60, 4.5), (70, 4.6), (80, 4.7), (90, 4.0), (100, 2.5),
       (110, 1.3), (130, 0.0), (150, -1.0), (180, -1.8), (200, -1.6), (250, -1.5), (300, -1.7), (380, -2.0), (480, 0.0)]
lf = np.log(np.clip(f1, 38, 480))
cible = np.interp(lf, np.log([p[0] for p in PTS]), [p[1] for p in PTS])
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def min_phase(G, n):
    c = np.fft.irfft(np.log(10 ** (G / 20)), N); w = np.zeros(N); w[0] = 1; w[1:N // 2] = 2; w[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * w, N)), N)[:n]
    fade = n // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


SOUS40 = "--sous40" in sys.argv; SUF = "grenat40" if SOUS40 else "grenat"
w = np.clip((f - 38) / 6, 0, 1) * (0.5 + 0.5 * np.cos(np.pi * np.clip(np.log(f1 / 400) / np.log(480 / 400), 0, 1)))
z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
res = {}
for ch in "LR":
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    avant = smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6); off = np.mean(avant[REF]); avant -= off
    delta = (cible - avant) * w
    for v in ("sanskick", "kick"):
        h0 = np.fromfile(os.path.join(D, "final", f"fir_{ch}_{v}_b7f76.raw"), "<f4").astype(float)
        G = db(np.fft.rfft(h0, N)) + delta
        if SOUS40:   # aucun renfort sous 40 Hz : FIR plafonne au niveau de son medium, rampe 40-46 Hz
            med = np.mean(G[(f >= 400) & (f <= 1000)])
            G = np.minimum(G, np.where(f < 40, med, np.where(f < 46, med + (G.max() - med) * (f - 40) / 6, np.inf)))
        h = min_phase(G, len(h0)); h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_{SUF}.raw"))
        if v == "sanskick":
            apres = smooth_db(db(base * np.fft.rfft(h, N)), 1 / 6) - off   # meme recalage qu'avant (rien ne bouge au-dessus de 480 Hz)
            res[ch] = (avant, apres)
            sel = (f >= 40) & (f <= 400)
            print(ch, "ecart au trait 40-400 Hz : avant", round(float(np.std((avant - cible)[sel])), 2), "apres", round(float(np.std((apres - cible)[sel])), 2),
                  "| crete", round(float(db(np.fft.rfft(h, N))[f < 20000].max()) - 20.5, 1), "dBFS")

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    a, b = res[ch]; m = (f >= 38) & (f <= 480)
    ax[j].plot(f[m], cible[m], color="#9b2335", lw=7, alpha=0.45, solid_capstyle="round", label="Trait grenat (cible)")
    ax[j].plot(f[1:], a[1:], color="#8a8a85", lw=1.4, ls="--", label="Avant : bosse +7 dB a 76 Hz")
    ax[j].plot(f[1:], b[1:], color="#2a78d6", lw=2.0, label="FIR vers le trait grenat" + (", rien sous 40 Hz" if SOUS40 else ""))
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (FIR sans kick, 1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 1000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else "1k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_xlabel("Hz")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[0].set_ylabel("dB")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=3, fontsize=10, frameon=False)
fig.suptitle("Cible « trait grenat » (version kick = meme grave, +0,8 dB entre 2 et 10 kHz)", fontsize=12)
fig.tight_layout(rect=(0, 0.06, 1, 1)); [a_.axvline(40, color="#9b2335", lw=0.8, ls="--") for a_ in ax] if SOUS40 else None
fig.savefig(os.path.join(D, f"{SUF}.png"), dpi=130)
