"""Comparaison pleine bande (20 Hz - 20 kHz) : avant la convolution / FIR sans kick / FIR kick.

- Avant : reglage EQ du 22/11 (creux renforces), calcule sur la mesure du 18/11 (k0_origine).
- FIR sans kick : mesure verif_bouton_sans (22/11, -40 dB, FIR final sans kick actif).
- FIR kick : meme mesure x (FIR kick / FIR sans kick) : exact pour une chaine lineaire.
Loudness inactive pendant les mesures. Micro non calibre : les ecarts entre courbes sont
justes, la pente absolue dans l'aigu depend aussi du micro. Recale 200-500 Hz.

    python3 correction/convolution/compare_aigu.py   -> compare_aigu.png
"""
import json, os, sys
import numpy as np, yaml
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "correction", "comparaison"))
from filtres import chain, FS
N = 1 << 17
f = np.fft.rfftfreq(N, 1 / FS); REF = (f >= 200) & (f <= 500)
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


ir = lambda l: (np.load(os.path.join(R, "mesure/resultats/ir", l + ".npz")), json.load(open(os.path.join(R, "mesure/resultats/ir", l + ".json")))["config"])
z0, k0 = ir("k0_origine"); z1, _ = ir("verif_bouton_sans")
avant = yaml.safe_load(open(os.path.join(R, "correction/comparaison/configs/4-actuel-creux-2026-11-22.yml")))
fir = lambda n: np.fft.rfft(np.fromfile(os.path.join(D, "final", n), "<f4").astype(float), N)
C = {}
for ch, i in (("L", 0), ("R", 1)):
    C[ch] = {
        "Avant : EQ du 22/11 (calcule, mesure 18/11)": np.fft.rfft(z0[ch], N) / chain(k0, i, f) * chain(avant, i, f),
        "FIR sans kick (mesure 22/11)": np.fft.rfft(z1[ch], N),
        "FIR kick (mesure x FIR kick / sans kick)": np.fft.rfft(z1[ch], N) * fir(f"fir_{ch}_kick.raw") / fir(f"fir_{ch}_sanskick.raw"),
    }
COL = ["#8a8a85", "#2a78d6", "#eb6834"]
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(2, 2, figsize=(15, 9.5), sharex=True)
bandes = [(300, 1500, "medium 300-1,5k"), (2000, 10000, "aigu 2-10k"), (10000, 18000, "extreme aigu 10-18k")]
resume = {}
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    s = {k: smooth_db(db(v), 1 / 6) for k, v in C[ch].items()}
    s = {k: v - np.mean(v[REF]) for k, v in s.items()}
    base = s["FIR sans kick (mesure 22/11)"]
    for k, (lab, v) in enumerate(s.items()):
        ax[0, j].plot(f[1:], v[1:], color=COL[k], lw=1.4 if k == 0 else 1.8, ls="--" if k == 0 else "-", label=lab)
    for k, (lab, v) in enumerate(s.items()):
        if lab.startswith("FIR sans"): continue
        d = v - base
        ax[1, j].plot(f[1:], d[1:], color=COL[k], lw=1.8, ls="--" if k == 0 else "-", label=lab + " - FIR sans kick")
    resume[ch] = {lab: {b[2]: round(float(np.mean((v - base)[(f >= b[0]) & (f <= b[1])])), 2) for b in bandes} for lab, v in s.items() if not lab.startswith("FIR sans")}
    ax[0, j].set_title(f"{nom} : reponse a la place d'ecoute (1/6 oct., recale 200-500 Hz)"); ax[0, j].set_ylim(-25, 20)
    ax[1, j].set_title(f"{nom} : difference par rapport au FIR sans kick"); ax[1, j].set_ylim(-10, 10)
for a in ax.flat:
    a.set_xscale("log"); a.set_xlim(20, 20000); a.axhline(0, color="#bbb", lw=0.8)
    t = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    a.set_xticks(t); a.set_xticklabels(["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); a.grid(True, color="#e6e6e3", lw=0.6); a.set_ylabel("dB")
    a.axvspan(2000, 20000, color="#f4f1ea", zorder=0)
    for sp in ("top", "right"): a.spines[sp].set_visible(False)
for a in ax[1]: a.set_xlabel("Hz")
h, l = ax[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, fontsize=9.5, frameon=False)
fig.suptitle("Pleine bande : avant la convolution, FIR sans kick, FIR kick (micro non calibre : comparer les ecarts)", fontsize=12)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(D, "compare_aigu.png"), dpi=130)
print(json.dumps(resume, indent=1, ensure_ascii=False))
