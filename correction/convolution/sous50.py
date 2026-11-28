"""23/11/2026 (Rulio12) : plus aucun renfort sous 50 Hz (au lieu de 40), sur les deux versions.
Meme methode que grenat.py --sous40 : gain du FIR plafonne au niveau de son medium (400-1000 Hz) sous 50 Hz,
rampe 50-56 Hz ; le reste (touche de grave kick, aigu redresse) ne change pas. Depart : FIR *_t120.

    python3 correction/convolution/sous50.py   -> final/fir_{L,R}_{sanskick,kick}_s50.raw, sous50.png
"""
import os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS)
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)


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
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])
    for v in ("sanskick", "kick"):
        h0 = np.fromfile(os.path.join(D, "final", f"fir_{ch}_{v}_t120.raw"), "<f4").astype(float)
        G = db(np.fft.rfft(h0, N)); med = np.mean(G[(f >= 400) & (f <= 1000)])
        top = G[(f >= 56) & (f <= 60)].mean()
        G2 = np.minimum(G, np.where(f < 50, med, np.where(f < 56, med + (max(top, med) - med) * (f - 50) / 6, np.inf)))
        h = min_phase(G2, len(h0)); h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_s50.raw"))
        Gh = db(np.fft.rfft(h, N))
        print(ch, v, "gain-medium 40/45/50/56/60/80 Hz", [round(float(Gh[np.argmin(abs(f - x))] - med), 1) for x in (40, 45, 50, 56, 60, 80)],
              "| ecart >70 Hz max", round(float(np.abs(Gh - G)[(f > 70) & (f < 20000)].max()), 2),
              "| crete", round(float(Gh[f < 20000].max()) - 20.5, 1), "dBFS")
    c = lambda n: smooth_db(db(base * fir(n)), 1 / 6) - off
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_t120.raw")[1:], color="#b9b8b2", lw=1.2, ls="--", label="Avant (sans kick, renfort des 40 Hz)")
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_s50.raw")[1:], color="#2a78d6", lw=2.0, label="Sans kick : rien sous 50 Hz")
    ax[j].plot(f[1:], c(f"fir_{ch}_kick_s50.raw")[1:], color="#eb6834", lw=1.4, label="Kick : rien sous 50 Hz, touche de grave jusqu'a 120 Hz, renfort 2-10 kHz")
    ax[j].axvline(50, color="#9b2335", lw=0.8, ls=":")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 20000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 50, 60, 100, 120, 200, 500, 1000, 2000, 5000, 10000, 20000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_ylabel("dB")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[1].set_xlabel("Hz")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=3, fontsize=10, frameon=False)
fig.suptitle("Courbe complete : aucun renfort sous 50 Hz (les deux versions)", fontsize=12)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(D, "sous50.png"), dpi=130)
