"""Les 4 corrections du grave archivees, et leur reponse attendue a la place d'ecoute.

Reponse attendue = mesure du 18/11 (resultats/ir/k0_origine, correction de l'epoque retiree)
x filtres de chaque correction. Tous les filtres sont comptes (Peaking, Lowshelf/Highshelf,
passe-haut Butterworth, FIR) sauf la loudness (depend du volume), le limiteur et les gains
constants (courbes recalees sur 200-1000 Hz). Moyenne 1/12 octave.

    python3 correction/comparaison/compare4.py   ->  correction/comparaison/compare4.png
"""
import json, os, subprocess, sys
import numpy as np, yaml
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "mesure"))
from sweep_dsp import band_average_db
FS = 44100
IGNORE = {"loud_bass", "loud_treble", "limiter"}

def git_yml(ref, path):
    return yaml.safe_load(subprocess.check_output(["git", "-C", R, "show", f"{ref}:{path}"]))

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

def biquad(b, a, f):
    z = np.exp(-1j * 2 * np.pi * f / FS)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)

def rbj(p, f):
    t, f0 = p["type"], p["freq"]; w = 2 * np.pi * f0 / FS; c, s = np.cos(w), np.sin(w)
    g = p.get("gain", 0); A = 10 ** (g / 40)
    if t == "Peaking":
        al = s / (2 * p["q"])
        return biquad([1 + al * A, -2 * c, 1 - al * A], [1 + al / A, -2 * c, 1 - al / A], f)
    if t in ("Lowshelf", "Highshelf"):
        if "q" in p: al = s / (2 * p["q"])
        else: al = s / 2 * np.sqrt((A + 1 / A) * (1 / (p["slope"] / 12) - 1) + 2)
        k = 2 * np.sqrt(A) * al
        if t == "Lowshelf":
            b = [A * ((A + 1) - (A - 1) * c + k), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - k)]
            a = [(A + 1) + (A - 1) * c + k, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - k]
        else:
            b = [A * ((A + 1) + (A - 1) * c + k), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - k)]
            a = [(A + 1) - (A - 1) * c + k, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - k]
        return biquad(b, a, f)
    raise ValueError(t)

def butter_hp(f0, order, f):
    h = np.ones(len(f), complex); w = 2 * np.pi * f0 / FS; c, s = np.cos(w), np.sin(w)
    for k in range(order // 2):
        q = 1 / (2 * np.cos(np.pi * (2 * k + 1) / (2 * order)))
        al = s / (2 * q)
        h *= biquad([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al], f)
    return h

def chain(cfg, ch, f):
    h = np.ones(len(f), complex)
    for st in cfg["pipeline"]:
        if st.get("type") != "Filter" or ch not in st.get("channels", []) or st.get("bypassed"):
            continue
        for n in st["names"]:
            if n in IGNORE: continue
            fl = cfg["filters"][n]; t, p = fl["type"], fl.get("parameters", {})
            if t == "Biquad" and p["type"] in ("Peaking", "Lowshelf", "Highshelf"):
                if p.get("gain"): h *= rbj(p, f)
            elif t == "BiquadCombo" and p["type"] == "ButterworthHighpass":
                h *= butter_hp(p["freq"], p["order"], f)
            elif t == "Conv":
                fir = np.fromfile(os.path.join(R, "mesure/fir", os.path.basename(p["filename"])), "<f4")
                h *= np.fft.rfft(fir, 2 * (len(f) - 1))[:len(f)] if len(fir) <= 2 * (len(f) - 1) else 1
            elif t in ("Gain", "Delay", "Limiter"):
                pass
            else:
                raise ValueError((n, t, p))
    return h

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
