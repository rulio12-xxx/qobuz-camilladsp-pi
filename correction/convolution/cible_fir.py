"""Correction du grave par convolution vers une courbe cible (22/11/2026).

Cible : forme de la reponse D avec l'EQ REW3 de juillet (bosse large ~58 Hz, +11 dB),
la meme pour G et D, au-dessus d'un passe-haut 32 Hz. La demande de grave est exageree :
les boosts sont multiplies par --exag (les reflexions de la piece font qu'un simple
delta cible/mesure ne rattrape pas tout). Au-dessus de 300 Hz, le FIR reprend la courbe de
l'EQ actuel (aigu, balance, pente) : rien d'autre n'est a ajouter apres la convolution.

    python3 correction/convolution/cible_fir.py [--exag 1.3] [--bosse 11] [--taps 16384]

Ecrit fir_L.raw / fir_R.raw (float32, 44,1 kHz, phase minimale), cible_fir.png, cible_fir.json
et camilladsp-qobuz-test-fir.yml dans ce dossier.
"""
import json, os, sys
import numpy as np, yaml
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "correction", "comparaison"))
from filtres import chain, rbj, butter_hp, FS

a = sys.argv[1:]
opt = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
EXAG, BOSSE, TAPS = opt("--exag", 1.3), opt("--bosse", 11.0), int(opt("--taps", 16384))
BOOST_MAX, BOOST_MAX_SOUS40, CUT_MAX = 15.0, 0.0, -20.0
MARGE = 6.0   # dB sous 0 dBFS au gain maxi du FIR (place pour la loudness)

N = 1 << 17
f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
z = np.load(os.path.join(R, "mesure/resultats/ir/k0_origine.npz"))
k0 = json.load(open(os.path.join(R, "mesure/resultats/ir/k0_origine.json")))["config"]
cur = yaml.safe_load(open(os.path.join(R, "camilladsp/camilladsp-qobuz.yml")))
rew = yaml.safe_load(open(os.path.join(R, "correction/test-juillet/camilladsp-qobuz-test-juillet.yml")))


def smooth_db(db, frac):
    p = 10 ** (db / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def db(h): return 20 * np.log10(np.abs(h) + 1e-12)


REF = (f >= 200) & (f <= 500)
# ---- cible relative (0 dB = niveau 200-500 Hz) ----
cible = db(rbj({"type": "Peaking", "freq": 58, "gain": BOSSE, "q": 0.8}, f)) \
    + db(rbj({"type": "Lowshelf", "freq": 110, "gain": 4.0, "q": 0.6}, f)) \
    + db(butter_hp(32, 4, f))
cible -= np.mean(cible[REF])


def min_phase(mag_db):
    """FIR a phase minimale (cepstre) depuis un module en dB sur la grille f."""
    logm = np.log(10 ** (mag_db / 20))
    c = np.fft.irfft(logm, N)
    w = np.zeros(N); w[0] = 1; w[1:N // 2] = 2; w[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * w, N)), N)[:TAPS]
    fade = TAPS // 8
    h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


res, firs = {}, {}
for ch, i in (("L", 0), ("R", 1)):
    raw = np.fft.rfft(z[ch], N) / chain(k0, i, f)           # salle + enceinte, sans correction
    eq_cur = chain(cur, i, f)                               # EQ actuel (hors gains constants)
    raw_s = smooth_db(db(raw), 1 / 6)
    lvl = np.mean(smooth_db(db(raw * eq_cur), 1 / 3)[REF])  # niveau actuel 200-500 Hz (equilibre G/D garde)
    delta = (cible + lvl) - raw_s
    boost = delta > 0
    bass = f < 150
    delta[boost & bass] *= EXAG                             # demande de grave exageree
    cap = BOOST_MAX_SOUS40 + (BOOST_MAX - BOOST_MAX_SOUS40) * np.clip((f - 36) / 8, 0, 1)   # 0 dB sous 36 Hz (sous l'accord de l'event) -> 15 dB a 44 Hz
    delta = np.minimum(delta, cap)
    delta = np.maximum(delta, CUT_MAX)
    # au-dessus de 300 Hz : courbe de l'EQ actuel, raccord 250-400 Hz
    haut = smooth_db(db(eq_cur), 1 / 6)
    w = np.clip(np.log(f1 / 250) / np.log(400 / 250), 0, 1); w = 0.5 - 0.5 * np.cos(np.pi * w)
    g = (1 - w) * delta + w * haut
    g[f < 15] = g[np.searchsorted(f, 15)] - 40 * np.log10(np.maximum(15 / f1[f < 15], 1))  # rien sous 15 Hz
    g = g + db(butter_hp(24, 4, f))                         # subsonique : protege le HP sous l'event
    g = smooth_db(g, 1 / 24)
    firs[ch] = g
    res[ch] = dict(raw=raw, raw_s=raw_s, lvl=lvl, eq_cur=eq_cur)

# niveau absolu : la musique garde le niveau actuel (preamp -20,5 dB) dans le medium,
# sauf si le gain maxi du FIR depasse -MARGE dBFS : tout descend alors d'autant.
PREAMP_CUR = cur["filters"]["preamp"]["parameters"]["gain"]
abs_db = {ch: firs[ch] + PREAMP_CUR for ch in firs}
pic = max(abs_db[ch][f < 20000].max() for ch in abs_db)
decal = min(0.0, -MARGE - pic)
out = {"exag": EXAG, "bosse": BOSSE, "taps": TAPS, "decalage_niveau_db": round(decal, 2), "voies": {}}
for ch, i in (("L", 0), ("R", 1)):
    h = min_phase(abs_db[ch] + decal).astype("<f4")
    h.tofile(os.path.join(D, f"fir_{ch}.raw"))
    H = np.fft.rfft(h.astype(float), N)
    pred = smooth_db(db(res[ch]["raw"] * H), 1 / 6)
    sel = (f >= 35) & (f <= 300)
    out["voies"][ch] = dict(gain_max_db=round(float(db(H)[f < 20000].max()), 1),
                            freq_gain_max=round(float(f[np.argmax(db(H)[f < 20000])]), 1),
                            ecart_cible_35_300=round(float(np.std(((pred - np.mean(pred[REF])) - cible)[sel])), 2))
    res[ch]["H"] = H; res[ch]["pred"] = pred
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(D, "cible_fir.json"), "w"), indent=1)

# ---- config de test : la meme que l'actuelle, toutes les corrections remplacees par le FIR ----
cfg = yaml.safe_load(open(os.path.join(R, "camilladsp/camilladsp-qobuz.yml")))
keep = {"loud_bass", "loud_treble", "delay_L", "delay_R", "limiter"}
filt = {k: v for k, v in cfg["filters"].items() if k in keep}
for ch in "LR":
    filt[f"fir_{ch}"] = {"type": "Conv", "description": "correction du grave vers la cible (correction/convolution/cible_fir.py, 22/11/2026)",
                         "parameters": {"type": "Raw", "filename": f"/home/rulio12/camilladsp/fir/cible_{ch}.raw", "format": "F32_LE"}}
cfg["filters"] = filt
cfg["title"] = "Qobuz - TEST convolution vers cible (forme REW3 D, grave exagere)"
cfg["description"] = f"FIR seul (exag {EXAG}, bosse {BOSSE} dB, {TAPS} points). Loudness et retards avant la convolution, rien apres hors lampes et limiteur."
cfg["pipeline"] = [
    {"type": "Filter", "channels": [0], "names": ["delay_L", "loud_bass", "loud_treble", "fir_L"]},
    {"type": "Filter", "channels": [1], "names": ["delay_R", "loud_bass", "loud_treble", "fir_R"]},
    {"type": "Processor", "name": "tube"},
    {"type": "Filter", "channels": [0, 1], "names": ["limiter"]},
]
yaml.safe_dump(cfg, open(os.path.join(D, "camilladsp-qobuz-test-fir.yml"), "w"), sort_keys=False, allow_unicode=True)

# ---- graphique ----
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
for j, (ch, i, nom) in enumerate((("L", 0, "Gauche"), ("R", 1, "Droite"))):
    r = res[ch]; m = lambda x: x - np.mean(x[REF])
    rw = m(r["raw_s"]); cu = m(smooth_db(db(r["raw"] * r["eq_cur"]), 1 / 6))
    rv = m(smooth_db(db(r["raw"] * chain(rew, i, f)), 1 / 6)); pr = m(r["pred"])
    a0 = ax[0, j]
    a0.plot(f, rw, color="#8a8a85", lw=1.3, ls="--", label="Sans correction")
    a0.plot(f, cu, color="#eda100", lw=1.6, label="Actuel (creux renforces)")
    a0.plot(f, rv, color="#eb6834", lw=1.6, label="EQ REW juillet")
    a0.plot(f, cible, color="#222", lw=2.4, ls=":", label="Cible")
    a0.plot(f, pr, color="#2a78d6", lw=2.2, label=f"FIR vers la cible (exag x{EXAG})")
    a0.set_title(f"{nom} : reponse attendue a la place d'ecoute (1/6 oct.)"); a0.set_ylim(-30, 20)
    a1 = ax[1, j]
    a1.plot(f, db(r["H"]) - np.mean(db(r["H"])[REF]), color="#2a78d6", lw=2, label="FIR")
    a1.plot(f, smooth_db(db(r["eq_cur"]), 1 / 6), color="#eda100", lw=1.6, label="EQ actuel")
    a1.set_title(f"{nom} : courbe du FIR"); a1.set_ylim(-25, 20)
for a_ in ax.flat:
    a_.set_xscale("log"); a_.set_xlim(20, 1000); a_.axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000]
    a_.set_xticks(t); a_.set_xticklabels(t); a_.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    a_.grid(True, color="#e6e6e3", lw=0.6); a_.set_ylabel("dB")
    for s in ("top", "right"): a_.spines[s].set_visible(False)
for a_ in ax[1]: a_.set_xlabel("Hz")
h, l = ax[0, 0].get_legend_handles_labels(); h2, l2 = ax[1, 0].get_legend_handles_labels()
fig.legend(h + h2[1:], l + ["EQ actuel (courbe)"], loc="lower center", ncol=6, fontsize=9, frameon=False)
fig.suptitle("Convolution vers une cible : forme REW3 droite, grave exagere, meme cible G et D", fontsize=12)
fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(os.path.join(D, "cible_fir.png"), dpi=130)
