"""Iterations mesure -> FIR vers la cible (22/11/2026).

A chaque tour : mesurer avec le FIR actif (`mesure/ir2.py mesure <etiquette>`), puis

    python3 correction/convolution/iter_fir.py <etiquette> [--alpha 0.7]

- lit la mesure (resultats/ir/<etiquette>.npz) et la config active au moment de la mesure ;
- retire la loudness (loud_bass / loud_treble actifs pendant la mesure) ;
- compare a la cible (cible.py), lissage 1/6 octave, recale sur 200-500 Hz ;
- corrige le FIR actif : G_nouveau = G_actuel + alpha x (cible - mesure), seulement de
  38 Hz (rampe jusqu'a 44 Hz) a 250 Hz (raccord jusqu'a 400 Hz) : le medium et l'aigu
  ne bougent pas, donc le niveau non plus ;
- plafonds : FIR <= +22 dB au-dessus de son medium, >= -25 dB ; crete <= 0 dBFS
  (sinon tout baisse et le script le dit) ;
- ecrit ~/camilladsp/fir/cible_{L,R}_i<n>.raw et met a jour
  ~/camilladsp/configs/camilladsp-qobuz-test-fir.yml (nouveaux noms : CamillaDSP relit le FIR au reload) ;
- garde l'historique dans iterations/etat.json et trace iterations/iter_<n>.png.

Options : --nom <prefixe> (fichiers <prefixe>_{L,R}_i<n>.raw, etat iterations/etat_<prefixe>.json),
--kick <dB> (bosse 78 Hz Q1,4 ajoutee a la cible), --clic <dB> (renfort 4,5 kHz Q1 applique une fois),
--lissage <n> (mesure en 1/n octave, 6 par defaut ; 12 pour affiner).
Le premier tour d'un nouveau --nom part du FIR actif de la mesure (ex. le FIR sans kick affine).

Recharger ensuite la config (set_file_path + reload) avant la mesure suivante.
--sim : simulation hors ligne (mesure = reponse du 18/11 x FIR), pour tester le script.
"""
import json, os, sys
import numpy as np, yaml
D = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(D, "..", "..")
sys.path.insert(0, os.path.join(R, "correction", "comparaison")); sys.path.insert(0, D)
from filtres import chain, rbj, FS
from cible import cible_db

a = sys.argv[1:]
opt = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
LABEL = a[0]; ALPHA = opt("--alpha", 0.7); SIM = "--sim" in a
KICK = opt("--kick", 0.0)        # dB : bosse du kick ajoutee a la cible (Peaking 78 Hz Q1,4)
CLIC = opt("--clic", 0.0)        # dB : renfort fixe du clic (Peaking 4,5 kHz Q1), hors iteration
LISSAGE = opt("--lissage", 6.0)  # mesure lissee en 1/LISSAGE octave
NOM = a[a.index("--nom") + 1] if "--nom" in a else "cible"   # prefixe des fichiers FIR et de l'etat
TAPS = 16384; N = 1 << 17
CAP_REL, CUT_REL, CRETE_MAX = 22.0, -25.0, 0.0   # crete : le volume (<= -20 dB) laisse la marge
FIRDIR = os.path.expanduser("~/camilladsp/fir"); CFG = os.path.expanduser("~/camilladsp/configs/camilladsp-qobuz-test-fir.yml")
IT = os.path.join(D, "iterations"); os.makedirs(IT, exist_ok=True)
ETAT = os.path.join(IT, "etat.json" if NOM == "cible" else f"etat_{NOM}.json")
f = np.fft.rfftfreq(N, 1 / FS); f1 = f.copy(); f1[0] = 1e-3
REF = (f >= 200) & (f <= 500); SEL = (f >= 38) & (f <= 300)
cible = cible_db(f)
if KICK:
    cible = cible + 20 * np.log10(np.abs(rbj({"type": "Peaking", "freq": 78, "gain": KICK, "q": 1.4}, f)))
db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)


def smooth_db(x, frac):
    p = 10 ** (x / 10); cs = np.concatenate([[0], np.cumsum(p)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2)); hi = np.maximum(np.searchsorted(f, f * 2 ** (frac / 2), side="right"), lo + 1)
    return 10 * np.log10((cs[hi] - cs[lo]) / (hi - lo))


def min_phase(mag_db):
    c = np.fft.irfft(np.log(10 ** (mag_db / 20)), N)
    w = np.zeros(N); w[0] = 1; w[1:N // 2] = 2; w[N // 2] = 1
    h = np.fft.irfft(np.exp(np.fft.rfft(c * w, N)), N)[:TAPS]
    fade = TAPS // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    return h


etat = json.load(open(ETAT)) if os.path.exists(ETAT) else {"iterations": []}
n = len(etat["iterations"])

# ---- mesure et FIR actif ----
if SIM:
    z = np.load(os.path.join(R, "mesure/resultats/ir/k0_origine.npz"))
    k0 = json.load(open(os.path.join(R, "mesure/resultats/ir/k0_origine.json")))["config"]
    fir_cur = {ch: np.fromfile(etat["iterations"][-1]["fichiers"][ch] if n else os.path.join(D, f"fir_{ch}.raw"), "<f4").astype(float) for ch in "LR"}
    meas = {ch: np.fft.rfft(z[ch], N) / chain(k0, i, f) * np.fft.rfft(fir_cur[ch], N) for ch, i in (("L", 0), ("R", 1))}
    volume = None
else:
    z = np.load(os.path.join(R, "mesure/resultats/ir", LABEL + ".npz"))
    meta = json.load(open(os.path.join(R, "mesure/resultats/ir", LABEL + ".json")))
    cfg = meta["config"]; volume = meta.get("volume")
    fir_cur, meas = {}, {}
    for ch, i in (("L", 0), ("R", 1)):
        fn = cfg["filters"][f"fir_{ch}"]["parameters"]["filename"]
        fir_cur[ch] = np.fromfile(fn, "<f4").astype(float)
        hl = np.ones(len(f), complex)
        for nm in ("loud_bass", "loud_treble"):
            p = cfg["filters"][nm]["parameters"]
            if p.get("gain"): hl *= rbj(p, f)
        meas[ch] = np.fft.rfft(z[ch], N) / hl

out = {"n": n, "etiquette": LABEL, "volume": volume, "alpha": ALPHA, "voies": {}, "fichiers": {}}
courbes = {}
w = np.clip((f - 38) / 6, 0, 1) * (0.5 + 0.5 * np.cos(np.pi * np.clip(np.log(f1 / 250) / np.log(400 / 250), 0, 1)))
G = {}
for ch in "LR":
    m = smooth_db(db(meas[ch]), 1 / LISSAGE); m -= np.mean(m[REF])
    err = cible - m
    g = db(np.fft.rfft(fir_cur[ch], N))
    gn = g + ALPHA * err * w
    if CLIC and not etat.get("clic_fait"):
        gn = gn + 20 * np.log10(np.abs(rbj({"type": "Peaking", "freq": 4500, "gain": CLIC, "q": 1.0}, f)))
    med = np.mean(gn[(f >= 400) & (f <= 1000)])
    gn = np.clip(gn, med + CUT_REL, med + CAP_REL)
    G[ch] = gn
    out["voies"][ch] = {"ecart_type_38_300": round(float(np.std(err[SEL])), 2),
                        "ecart_max_38_300": round(float(np.max(np.abs(err[SEL]))), 1),
                        "ecart_moyen_45_100": round(float(np.mean(err[(f >= 45) & (f <= 100)])), 1)}
    courbes[ch] = m
crete = max(G[ch][(f > 15) & (f < 20000)].max() for ch in "LR")
baisse = min(0.0, CRETE_MAX - crete)
out["baisse_niveau_db"] = round(baisse, 2)
for ch in "LR":
    h = min_phase(G[ch] + baisse).astype("<f4")
    fn = (os.path.join(IT, f"sim_{NOM}_{ch}_i{n + 1}.raw") if SIM else os.path.join(FIRDIR, f"{NOM}_{ch}_i{n + 1}.raw"))
    h.tofile(fn); out["fichiers"][ch] = fn
    out["voies"][ch]["crete_fir_dbfs"] = round(float(db(np.fft.rfft(h.astype(float), N))[f < 20000].max()), 1)

# historique (courbes sur grille 1/24 oct.) et config mise a jour
grid = [20 * 2 ** (k / 24) for k in range(0, 24 * 6) if 20 * 2 ** (k / 24) <= 1000]
gi = [int(np.argmin(abs(f - x))) for x in grid]
out["courbes"] = {ch: [round(float(courbes[ch][j]), 2) for j in gi] for ch in "LR"}
out["grille"] = [round(x, 2) for x in grid]
if CLIC: etat["clic_fait"] = True
out.update(kick=KICK, clic=CLIC, lissage=LISSAGE)
etat["iterations"].append(out); json.dump(etat, open(ETAT, "w"))
if not SIM:
    y = yaml.safe_load(open(CFG))
    for ch in "LR":
        y["filters"][f"fir_{ch}"]["parameters"]["filename"] = out["fichiers"][ch]
    y["description"] = f"FIR iteration {n + 1} (correction/convolution/iter_fir.py, mesure {LABEL})"
    yaml.safe_dump(y, open(CFG, "w"), sort_keys=False, allow_unicode=True)

print(json.dumps({k: v for k, v in out.items() if k not in ("courbes", "grille")}, indent=1, ensure_ascii=False))
print("-> recharger", CFG if not SIM else "(simulation)")

# ---- graphique : cible et chaque mesure ----
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.ticker
fig, ax = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
its = etat["iterations"]; ci = [int(np.argmin(abs(f - x))) for x in grid]
for j, (ch, nom) in enumerate((("L", "Gauche"), ("R", "Droite"))):
    A = ax[j]
    A.plot(grid, cible[ci], color="#222", lw=2.4, ls=":", label="Cible")
    for k, it in enumerate(its):
        last = k == len(its) - 1
        A.plot(it["grille"], it["courbes"][ch], lw=2.2 if last else 1.1,
               color="#2a78d6" if last else plt.cm.Greys(0.35 + 0.4 * k / max(1, len(its) - 1)),
               label=f"Mesure {k} ({it['etiquette']}) : ecart {it['voies'][ch]['ecart_type_38_300']} dB" if (last or k == 0) else None)
    A.set_title(f"{nom} : mesures successives (1/6 oct., recale 200-500 Hz)")
    A.set_xscale("log"); A.set_xlim(20, 1000); A.set_ylim(-30, 20); A.axhline(0, color="#bbb", lw=0.8)
    t = [20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 1000]
    A.set_xticks(t); A.set_xticklabels(t); A.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    A.grid(True, color="#e6e6e3", lw=0.6); A.set_xlabel("Hz"); A.legend(fontsize=8.5, frameon=False, loc="lower right")
    for s in ("top", "right"): A.spines[s].set_visible(False)
ax[0].set_ylabel("dB")
fig.suptitle(f"Convolution vers la cible{' + kick ' + str(KICK) + ' dB' if KICK else ''} : iteration {n} (ecart-type 38-300 Hz)", fontsize=12)
fig.tight_layout(); fig.savefig(os.path.join(IT, f"{'sim_' if SIM else ''}{'' if NOM == 'cible' else NOM + '_'}iter_{n}.png"), dpi=120)
