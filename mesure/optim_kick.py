"""Optimiseur oriente kick, sur le modele des reponses impulsionnelles (ir2.py).

    python3 optim_kick.py <etiquette_ir> [--poids-clic 1] [--sans-clic-boost]

Variables : gain/freq/Q des filtres de grave propres a chaque voie (<= 250 Hz)
et du click_boost (partage, <= +5 dB). Cout :
  - courbe du grave (45-220 Hz) des deux voies vers la cible (+2 dB 50-90 Hz, puis plat)
  - 2 x ecart G-D
  - kick G+D : clic relatif vers 0 dB (comme le fichier), bavure (plus bas = mieux),
    retard du corps (plus court = mieux), traine vers 0 dB
  - sobriete : renforts plus chers que les coupes, Q <= 5, gain <= +6 dB
Affiche avant/apres et la ligne CHANGEMENTS a passer a regle.py / ir2.py predit.
"""
import copy
import json
import sys

import numpy as np

import ir2
import kick2

label = sys.argv[1]
W_CLIC = float(sys.argv[sys.argv.index("--poids-clic") + 1]) if "--poids-clic" in sys.argv else 1.0
USE_CB = "--sans-clic-boost" not in sys.argv
BOSSE = float(sys.argv[sys.argv.index("--bosse") + 1]) if "--bosse" in sys.argv else 4.0
CLIC_CIBLE = float(sys.argv[sys.argv.index("--clic") + 1]) if "--clic" in sys.argv else 2.0
FS = ir2.FS
irs, meta = ir2.load(label)
cfg = meta["config"]

n_seg = int(0.6 * FS)
L_ir = len(irs["L"])
nf = 1 << (n_seg + L_ir - 1).bit_length()
f = np.fft.rfftfreq(nf, 1 / FS)
src = kick2.make_kick()
src_pad = np.concatenate([src, np.zeros(n_seg - len(src))])
K = np.fft.rfft(src_pad, nf)
X = {ch: np.fft.rfft(irs[ch], nf) for ch in ("L", "R")}
pre = int(ir2.PRE_MS / 1000 * FS)

# bandes 1/12 oct pour la courbe
fc = np.array(ir2.CENTERS)
b_lo = np.searchsorted(f, fc * 2 ** (-1 / 24))
b_hi = np.searchsorted(f, fc * 2 ** (1 / 24))
fit = (fc >= 45) & (fc <= 220)
mid = (fc >= 300) & (fc <= 3000)   # reference de niveau hors de portee des filtres de grave
target = np.interp(np.log(fc), np.log([45, 50, 100, 140, 220]), [BOSSE, BOSSE, BOSSE, 0, 0])

SHARED = {"notch_42", "notch_64", "treble_air", "loud_bass", "loud_treble", "click_boost"}


def names(idx):
    out = []
    for s in cfg["pipeline"]:
        if s.get("type") == "Filter" and s.get("channels") == [idx]:
            out += s["names"]
    return out


free = {}
for ch, idx in (("L", 0), ("R", 1)):
    free[ch] = [n for n in names(idx) if cfg["filters"][n]["type"] == "Biquad"
                and cfg["filters"][n]["parameters"].get("type") == "Peaking"
                and n not in SHARED and cfg["filters"][n]["parameters"]["freq"] <= 250]
shared_free = ["click_boost"] if USE_CB else []
allfree = sorted(set(free["L"] + free["R"] + shared_free))
init = {n: dict(cfg["filters"][n]["parameters"]) for n in allfree}
lim_f = {n: ((max(40.0, init[n]["freq"] / 1.3), min(230.0, init[n]["freq"] * 1.3))
             if n != "click_boost" else (1800.0, 4500.0)) for n in allfree}
H_old = {ch: ir2.chain_h(cfg, idx, f) for ch, idx in (("L", 0), ("R", 1))}


def h(p):
    return ir2.peaking_h(f, p["freq"], p["gain"], p["q"]) if p["gain"] else np.ones(len(f), complex)


# reponse des filtres libres dans l'etat initial, par voie
def free_h(P, ch):
    out = np.ones(len(f), complex)
    for n in free[ch] + shared_free:
        out *= h(P[n])
    return out


H_free0 = {ch: free_h(init, ch) for ch in ("L", "R")}
# reponse de chaque filtre libre, mise a jour seulement quand il change
H_each = {n: h(init[n]) for n in allfree}
H_prod = {ch: free_h(init, ch) for ch in ("L", "R")}
BASE = {ch: X[ch] / H_free0[ch] for ch in ("L", "R")}   # mesure sans les filtres libres


def evaluate(P, changed=None):
    if changed is None:
        Hp = {ch: free_h(P, ch) for ch in ("L", "R")}
    else:
        hn = h(P[changed])
        Hp = {ch: (H_prod[ch] / H_each[changed] * hn if changed in free[ch] + shared_free else H_prod[ch])
              for ch in ("L", "R")}
    Y = {ch: BASE[ch] * Hp[ch] for ch in ("L", "R")}
    # courbes
    cur = {}
    for ch in ("L", "R"):
        cs = np.concatenate([[0.0], np.cumsum(np.abs(Y[ch]) ** 2)])
        with np.errstate(divide="ignore", invalid="ignore"):
            v = 10 * np.log10((cs[b_hi] - cs[b_lo]) / np.maximum(b_hi - b_lo, 1) + 1e-30)
        v[b_hi <= b_lo] = np.nan
        cur[ch] = v - np.nanmean(v[mid])
    # kick G+D simule
    y = np.fft.irfft(K * (Y["L"] + Y["R"]), nf)[pre:pre + n_seg]
    m = metrics(y)
    return cur, m


hf_s = kick2.band(src_pad, *kick2.CLIC_BAND)
lf_s = kick2.band(src_pad, *kick2.CORPS_BAND)
Es_ratio = 10 * np.log10(np.sum(hf_s[:int(0.006 * FS)] ** 2) / np.sum(lf_s[:int(0.3 * FS)] ** 2))
el_s = kick2.envelope(lf_s, 8)
on_s = int(np.argmax(el_s >= el_s.max() * 0.5))
nl_s = kick2.db(el_s / el_s.max())


def metrics(y):
    hf, lf = kick2.band(y, *kick2.CLIC_BAND), kick2.band(y, *kick2.CORPS_BAND)
    eh = kick2.envelope(hf, 0.3)
    ic = int(np.argmax(eh[:int(0.03 * FS)]))
    Ec = np.sum(hf[max(0, ic - int(0.001 * FS)):ic + int(0.006 * FS)] ** 2)
    El = np.sum(hf[ic + int(0.006 * FS):ic + int(0.040 * FS)] ** 2)
    Eb = np.sum(lf[:int(0.3 * FS)] ** 2)
    el = kick2.envelope(lf, 8)
    on = int(np.argmax(el >= el.max() * 0.5))
    nl = kick2.db(el / el.max())
    a, b = int(0.06 * FS), int(0.3 * FS)
    return {"clic": 10 * np.log10(Ec / Eb) - Es_ratio, "bavure": 10 * np.log10(El / Ec),
            "retard": (on - ic - on_s) / FS * 1000, "traine": float(np.mean(nl[a:b] - nl_s[a:b]))}


def cost(P, detail=False, changed=None):
    cur, m = evaluate(P, changed)
    e_curve = sum(np.nanmean((cur[ch][fit] - target[fit]) ** 2) for ch in ("L", "R"))
    e_lr = 2 * np.nanmean((cur["L"][fit] - cur["R"][fit]) ** 2)
    e_kick = (W_CLIC * 1.5 * min(m["clic"] - CLIC_CIBLE, 0) ** 2 + 0.5 * max(m["clic"] - CLIC_CIBLE - 2, 0) ** 2
              + 1.0 * m["bavure"] + 0.4 * max(m["retard"], 0) + 0.5 * m["traine"] ** 2)
    e_sob = 0.0
    for n, p in P.items():
        e_sob += (0.25 * p["gain"] if p["gain"] > 0 else 0.03 * -p["gain"])
        gmax = 3.0 if n == "click_boost" else 6.0
        e_sob += 5 * max(0, p["gain"] - gmax) ** 2 + 3 * max(0, p["q"] - 5.0) ** 2
    tot = e_curve + e_lr + e_kick + e_sob
    if detail:
        return tot, {"courbe": e_curve, "GD": e_lr, "kick": e_kick, "sobriete": e_sob}, cur, m
    return tot


P = copy.deepcopy(init)
best = cost(P)
c0 = best
steps = {"gain": 1.0, "freq": 0.06, "q": 0.25}
for it in range(40):
    improved = False
    for n in allfree:
        for k in ("gain", "freq", "q"):
            for sgn in (+1, -1):
                Q = copy.deepcopy(P)
                if k == "freq":
                    Q[n][k] = float(np.clip(Q[n][k] * (1 + sgn * steps[k]), *lim_f[n]))
                elif k == "q":
                    Q[n][k] = float(np.clip(Q[n][k] * (1 + sgn * steps[k]), 1.0 if n != "click_boost" else 0.7, 8))
                else:
                    Q[n][k] = float(np.clip(Q[n][k] + sgn * steps[k], -18, 7))
                c = cost(Q, changed=n)
                if c < best - 1e-6:
                    P, best, improved = Q, c, True
                    hn = h(P[n])
                    for ch in ("L", "R"):
                        if n in free[ch] + shared_free:
                            H_prod[ch] = H_prod[ch] / H_each[n] * hn
                    H_each[n] = hn
    print(f"passe {it + 1} : cout {best:.2f}", flush=True)
    if not improved:
        steps = {k: v / 2 for k, v in steps.items()}
        if steps["gain"] < 0.1:
            break

for name, PP in (("avant", init), ("apres", P)):
    tot, parts, cur, m = cost(PP, detail=True)
    lr = np.abs(cur["L"][fit] - cur["R"][fit])
    print(f"{name} : cout {tot:.1f} ({', '.join(f'{k} {v:.1f}' for k, v in parts.items())})")
    print(f"   kick G+D : clic {m['clic']:+.2f} dB, bavure {m['bavure']:+.2f} dB, "
          f"retard corps {m['retard']:+.2f} ms, traine {m['traine']:+.2f} dB ; "
          f"grave : ecart G-D moyen {np.nanmean(lr):.1f} dB (max {np.nanmax(lr):.1f})")
chg = []
for n in allfree:
    for k in ("gain", "freq", "q"):
        a, b = init[n][k], P[n][k]
        if abs(a - b) > (0.05 if k == "gain" else 0.005 * a if k == "freq" else 0.02):
            chg.append(f"{n}.{k}={round(b, 1) if k != 'q' else round(b, 2)}")
print("CHANGEMENTS " + " ".join(chg))
