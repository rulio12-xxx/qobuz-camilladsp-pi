"""23/11/2026 (Rulio12) : 1) version kick : petite touche de grave 40-120 Hz (+2 dB, plateau 45-100 Hz,
retour a 0 a 130 Hz, rien sous 40 Hz) ; la version sans kick ne change pas dans le grave.
2) les deux versions : pente au-dessus de 10 kHz redressee de moitie (renfort = moitie de l'ecart a 0 dB,
mesure lissee 1/3 oct., rampe 9-10,5 kHz, plafond +6 dB). Micro non calibre : l'aigu mesure est a prendre avec prudence.
Depart : FIR *_l456.

    python3 correction/convolution/touche.py   -> final/fir_{L,R}_{sanskick,kick}_t120.raw, touche.png
"""
import os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
FS = 44100; N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)
lg = lambda a, b: np.clip(np.log(f1 / a) / np.log(b / a), 0, 1)
cos_up = lambda a, b: 0.5 - 0.5 * np.cos(np.pi * lg(a, b))


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def min_phase(G, n):
    c = np.fft.irfft(np.log(10 ** (G / 20)), N); ww = np.zeros(N); ww[0] = 1; ww[1:N // 2] = 2; ww[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * ww, N)), N)[:n]
    fade = n // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


grave = 2.0 * cos_up(40, 45) * (1 - cos_up(100, 130))       # touche de grave du kick
z = np.load(os.path.join(R, "mesure/resultats/ir/verif_bouton_sans.npz"))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    base = np.fft.rfft(z[ch], N) / fir(f"fir_{ch}_sanskick_avant38.raw")
    off = np.mean(smooth_db(db(base * fir(f"fir_{ch}_sanskick_b7f76.raw")), 1 / 6)[REF])
    r3 = smooth_db(db(base * fir(f"fir_{ch}_sanskick_l456.raw")), 1 / 3) - off
    aigu = np.clip(-0.5 * r3, 0, 6.0) * cos_up(9000, 10500)
    aigu[f > 21000] = aigu[np.searchsorted(f, 21000)]
    for v, extra in (("sanskick", aigu), ("kick", aigu + grave)):
        h0 = np.fromfile(os.path.join(D, "final", f"fir_{ch}_{v}_l456.raw"), "<f4").astype(float)
        h = min_phase(db(np.fft.rfft(h0, N)) + extra, len(h0)); h.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_t120.raw"))
        print(ch, v, "renfort aigu 12/16/20 kHz", [round(float(aigu[np.argmin(abs(f - x))]), 1) for x in (12000, 16000, 20000)],
              "| grave 40/60/100/130", [round(float(extra[np.argmin(abs(f - x))]), 1) for x in (40, 60, 100, 130)],
              "| crete", round(float(db(np.fft.rfft(h, N))[f < 20000].max()) - 20.5, 1), "dBFS")
    c = lambda n: smooth_db(db(base * fir(n)), 1 / 6) - off
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_l456.raw")[1:], color="#b9b8b2", lw=1.2, ls="--", label="Avant (sans kick)")
    ax[j].plot(f[1:], c(f"fir_{ch}_sanskick_t120.raw")[1:], color="#2a78d6", lw=2.0, label="Sans kick : aigu redresse de moitie")
    ax[j].plot(f[1:], c(f"fir_{ch}_kick_t120.raw")[1:], color="#eb6834", lw=1.4, label="Kick : + touche de grave 40-120 Hz + renfort 2-10 kHz")
    ax[j].axvline(40, color="#9b2335", lw=0.8, ls=":")
    ax[j].set_title(f"{nom} : reponse attendue a la place d'ecoute (1/6 oct.)")
    ax[j].set_xscale("log"); ax[j].set_xlim(20, 20000); ax[j].set_ylim(-25, 20); ax[j].axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 60, 100, 120, 200, 500, 1000, 2000, 5000, 10000, 20000]
    ax[j].set_xticks(t); ax[j].set_xticklabels([str(x) if x < 1000 else f"{x // 1000}k" for x in t])
    ax[j].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax[j].grid(True, color="#e6e6e3", lw=0.6); ax[j].set_ylabel("dB")
    for sp in ("top", "right"): ax[j].spines[sp].set_visible(False)
ax[1].set_xlabel("Hz")
h_, l_ = ax[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=3, fontsize=10, frameon=False)
fig.suptitle("Courbe complete : aigu au-dessus de 10 kHz redresse de moitie ; kick avec touche de grave 40-120 Hz", fontsize=12)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(D, "touche.png"), dpi=130)
