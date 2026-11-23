"""23/11/2026 (Rulio12) : remettre le FIR commun du mercredi 18/11 (correction de phase du grave,
mesure/fir/phase_L.raw = phase_R.raw, passe-tout, avance le grave de 80 % du retard de l'enceinte,
retard global 60 ms identique sur les deux voies) par-dessus la convolution actuelle *_s50.
Les deux filtres sont fusionnes en un seul FIR par voie (32768 coefficients) : aucun changement de YAML,
le bouton Kick continue de basculer entre sanskick et kick.

    python3 correction/convolution/phase18.py   -> final/fir_{L,R}_{sanskick,kick}_s50p18.raw, phase18.png
"""
import os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS)
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
rd = lambda p: np.fromfile(p, "<f4").astype(float)
ph = rd(os.path.join(R, "mesure/fir/phase_L.raw"))
assert np.array_equal(ph, rd(os.path.join(R, "mesure/fir/phase_R.raw")))
gd = lambda H: -np.gradient(np.unwrap(np.angle(H)), 2 * np.pi * f[1]) * 1000


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig = plt.figure(figsize=(15, 9)); gs = fig.add_gridspec(2, 2, width_ratios=[2.2, 1])
ax = np.empty((2, 2), dtype=object); ax[0, 0] = fig.add_subplot(gs[0, 0]); ax[1, 0] = fig.add_subplot(gs[1, 0], sharex=ax[0, 0])
ax[0, 1] = ax[1, 1] = fig.add_subplot(gs[:, 1])
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    fa = lambda n: np.fft.rfft(rd(os.path.join(D, "final", n)), N)
    base = np.fft.rfft(z[ch], N) / fa(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fa(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])
    for v in ("sanskick", "kick"):
        h0 = rd(os.path.join(D, "final", f"fir_{ch}_{v}_s50.raw"))
        h = np.zeros(32768); c = np.convolve(h0, ph); h[:len(c)] = c
        h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_s50p18.raw"))
        d = (db(np.fft.rfft(h, N)) - db(np.fft.rfft(h0, N)))[(f > 20) & (f < 20000)]
        print(ch, v, "niveau change de", round(float(d.min()), 2), "a", round(float(d.max()), 2), "dB | crete",
              round(float(db(np.fft.rfft(h, N))[f < 20000].max()) - 20.5, 1), "dBFS")
    a = base * fa(f"fir_{ch}_kick_s50.raw"); b = base * fa(f"fir_{ch}_kick_s50p18.raw")
    ax[j, 0].plot(f[1:], (smooth_db(db(a), 1 / 6) - off)[1:], color="#b9b8b2", lw=2.4, label="Actuel (kick, rien sous 50 Hz)")
    ax[j, 0].plot(f[1:], (smooth_db(db(b), 1 / 6) - off)[1:], color="#eb6834", lw=1.2, label="+ FIR commun du 18/11 (phase du grave)")
    ax[j, 0].set_title(f"{nom} : niveau a la place d'ecoute (1/6 oct.)"); ax[j, 0].set_ylim(-25, 15)
    if j == 0:
        av = 60 - gd(np.fft.rfft(ph, N)); av = np.convolve(np.ones(9) / 9, av, "same")
        ax[0, 1].plot(f[1:], av[1:], color="#eb6834", lw=2.0)
        ax[0, 1].set_title("Ce que fait le FIR du 18/11 (meme sur G et D) :\navance du grave par rapport a l'aigu (ms)", fontsize=10)
        ax[0, 1].set_xlim(25, 1000); ax[0, 1].set_ylim(-2, 30); ax[0, 1].set_ylabel("ms")
    for c_, t in ((0, [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]), (1, [30, 50, 100, 200, 500, 1000])):
        A = ax[j, c_]; A.set_xscale("log"); A.set_xticks(t); A.set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
        A.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); A.grid(True, color="#e6e6e3", lw=0.6); A.axhline(0, color="#bbb", lw=0.8)
        for sp in ("top", "right"): A.spines[sp].set_visible(False)
    ax[j, 0].set_xlim(20, 20000); ax[j, 0].set_ylabel("dB")
ax[1, 0].set_xlabel("Hz"); ax[0, 1].set_xlabel("Hz")
h_, l_ = ax[0, 0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=2, fontsize=10, frameon=False)
fig.suptitle("FIR commun du 18/11 (phase du grave) ajoute a la convolution actuelle : niveau inchange, grave remis a l'heure", fontsize=12)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(D, "phase18.png"), dpi=130)
