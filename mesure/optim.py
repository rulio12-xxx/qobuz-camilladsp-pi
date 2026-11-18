"""Optimise les filtres de grave existants (gain, frequence, Q) de chaque voie
pour approcher une cible, a partir d'une mesure (predicteur exact, cf predit.py).

    python3 optim.py resultats/<campagne> [--fmax 250] [--bosse 2]

Cout = ecart a la cible (45-220 Hz, 1/12 oct) des deux voies
     + 2 x ecart G-D
     + penalites : renfort > +6 dB, Q > 6, et petite penalite sur chaque dB de
       filtre (prefere des corrections sobres, moins de retard de groupe).
Les filtres partages (notches, clic, aigu) et ceux au-dessus de --fmax ne bougent pas.
Sortie : la liste filtre.param=valeur a passer a iter.sh / predit.py.
"""
import copy
import json
import os
import sys

import numpy as np

from courbes import peaking_db, CENTERS

args = sys.argv[1:]
d = args[0]
FMAX = float(args[args.index("--fmax") + 1]) if "--fmax" in args else 250.0
BOSSE = float(args[args.index("--bosse") + 1]) if "--bosse" in args else 2.0
GMAX, QMAX = 6.0, 5.0

res = json.load(open(os.path.join(d, "niveaux.json")))
cfg = json.load(open(os.path.join(d, "config_active.json")))["config"]
vol = sorted(res["niveaux"], key=float)[-1]
f = np.array(CENTERS)
mid = (f >= 200) & (f <= 1000)
fit = (f >= 45) & (f <= 220)
target = np.interp(np.log(f), np.log([45, 50, 90, 120, 220]), [BOSSE, BOSSE, BOSSE, 0, 0])

SHARED = {"notch_42", "notch_64", "click_boost", "treble_air", "loud_bass", "loud_treble"}


def chan_filters(idx):
    names = []
    for s in cfg["pipeline"]:
        if s.get("type") == "Filter" and s.get("channels") == [idx]:
            names += s["names"]
    return names


def resp(p):
    return peaking_db(f, p["freq"], p["gain"], p["q"]) if p["gain"] else np.zeros(len(f))


room, free, fixed_resp = {}, {}, {}
for ch, idx in (("L", 0), ("R", 1)):
    names = chan_filters(idx)
    meas = np.array([np.nan if v is None else v for v in res["niveaux"][vol][ch]["bands_12"]])
    tot = np.zeros(len(f))
    fr = np.zeros(len(f))
    free[ch] = []
    for n in names:
        flt = cfg["filters"][n]
        p = flt["parameters"]
        if flt["type"] == "Biquad" and p.get("type") == "Peaking":
            r = resp(p)
            tot += r
            if n not in SHARED and p["freq"] <= FMAX:
                free[ch].append(n)
            else:
                fr += r
        elif flt["type"] == "Gain":
            pass
    sm = meas.copy()                # lissage 1/4 oct (3 points au 1/12 oct)
    sm[1:-1] = np.nanmean(np.vstack([meas[:-2], meas[1:-1], meas[2:]]), axis=0)
    room[ch] = sm - tot             # piece + HP sans aucune correction
    fixed_resp[ch] = fr

init = {n: dict(cfg["filters"][n]["parameters"]) for ch in free for n in free[ch]}
lim = {n: (max(40.0, init[n]["freq"] / 1.3), min(230.0, init[n]["freq"] * 1.3)) for n in init}


def curves(P):
    out = {}
    for ch in ("L", "R"):
        c = room[ch] + fixed_resp[ch] + sum(resp(P[n]) for n in free[ch])
        out[ch] = c - np.nanmean(c[mid])
    return out


def cost(P):
    c = curves(P)
    e = 0.0
    for ch in ("L", "R"):
        e += np.nanmean((c[ch][fit] - target[fit]) ** 2)
    e += 2 * np.nanmean((c["L"][fit] - c["R"][fit]) ** 2)
    for n, p in P.items():
        # un renfort coute plus qu'une coupe (excursion, retard de groupe, resonance)
        e += (0.25 * p["gain"] if p["gain"] > 0 else 0.03 * -p["gain"])
        e += 5 * max(0, p["gain"] - GMAX) ** 2 + 3 * max(0, p["q"] - QMAX) ** 2
    return e


P = copy.deepcopy(init)
best = cost(P)
c0 = best
steps = {"gain": 1.0, "freq": 0.06, "q": 0.25}
for it in range(60):
    improved = False
    for n in P:
        for k in ("gain", "freq", "q"):
            for sgn in (+1, -1):
                Q = copy.deepcopy(P)
                if k == "freq":
                    Q[n][k] = float(np.clip(Q[n][k] * (1 + sgn * steps[k]), *lim[n]))
                elif k == "q":
                    Q[n][k] = float(np.clip(Q[n][k] * (1 + sgn * steps[k]), 0.7, 10))
                else:
                    Q[n][k] = float(np.clip(Q[n][k] + sgn * steps[k], -18, GMAX + 1))
                c = cost(Q)
                if c < best - 1e-6:
                    P, best, improved = Q, c, True
    if not improved:
        steps = {k: v / 2 for k, v in steps.items()}
        if steps["gain"] < 0.05:
            break

chg = []
for n in P:
    for k in ("gain", "freq", "q"):
        a, b = init[n][k], P[n][k]
        if abs(a - b) > (0.05 if k == "gain" else 0.005 * a if k == "freq" else 0.02):
            chg.append(f"{n}.{k}={round(b, 1) if k != 'q' else round(b, 2)}")
c_init, c_fin = curves(init), curves(P)
for name, c in (("avant", c_init), ("apres", c_fin)):
    lr = np.abs(c["L"][fit] - c["R"][fit])
    dl = np.abs(np.r_[c["L"][fit] - target[fit], c["R"][fit] - target[fit]])
    print(f"{name} : ecart a la cible moyen {np.nanmean(dl):.1f} dB (max {np.nanmax(dl):.1f}) ; "
          f"ecart G-D moyen {np.nanmean(lr):.1f} dB (max {np.nanmax(lr):.1f})")
print(f"cout {c0:.2f} -> {best:.2f}")
print("CHANGEMENTS " + " ".join(chg))
