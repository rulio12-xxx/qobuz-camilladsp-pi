"""FIR de correction de phase du grave (passe-tout), par voie, depuis une mesure ir2.

    python3 fir.py <etiquette_ir> [--part 0.8] [--fmax 250] [--retard 60] [--taps 16384] [--ecrire]

Principe : retard de groupe de chaque enceinte (relatif a l'arrivee de l'aigu),
lisse au 1/3 d'octave pour ne garder que le comportement large (haut-parleur,
events, filtres), entre 25 Hz et --fmax ; le FIR avance le grave d'une part
(--part) de ce retard, sans toucher au niveau. Un retard global (--retard ms,
identique sur les deux voies) rend le filtre realisable : toute la musique est
retardee d'autant, l'equilibre G/D ne change pas.
Affiche le retard de groupe avant/apres et l'effet predit sur le kick.
--ecrire : ecrit ~/camilladsp/fir/phase_L.raw et phase_R.raw (float32, 44,1 kHz).
"""
import os
import sys

import numpy as np

import ir2
import kick2

a = sys.argv[1:]
label = a[0]
opt = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
PART, FMAX, D_MS, TAPS = opt("--part", 0.8), opt("--fmax", 250.0), opt("--retard", 60.0), int(opt("--taps", 16384))
FS = ir2.FS
irs, meta = ir2.load(label)
N = 1 << 17
f = np.fft.rfftfreq(N, 1 / FS)
D = D_MS / 1000


def arrival(ir):
    h = kick2.envelope(kick2.band(ir, 1000, 16000), 0.05)
    return int(np.argmax(h[:int(0.05 * FS)])) / FS


def smooth_complex(H, frac):
    """lissage complexe en fraction d'octave (moyenne glissante en log f)."""
    out = H.copy()
    cs = np.concatenate([[0], np.cumsum(H)])
    lo = np.searchsorted(f, f * 2 ** (-frac / 2))
    hi = np.searchsorted(f, f * 2 ** (frac / 2), side="right")
    hi = np.maximum(hi, lo + 1)
    out = (cs[hi] - cs[lo]) / (hi - lo)
    return out


def group_delay(H):
    ph = np.unwrap(np.angle(H))
    return -np.gradient(ph, 2 * np.pi * f)


firs, report = {}, {}
COMMUN = "--commun" in a      # un seul FIR, calcule sur la somme G+D, pour les deux voies
for ch in ("L", "R"):
    ir = irs["L"] + irs["R"] if COMMUN else irs[ch]
    t0 = arrival(ir)
    H = np.fft.rfft(ir, N) * np.exp(1j * 2 * np.pi * f * t0)     # temps 0 = arrivee de l'aigu
    Hs = smooth_complex(H, 1 / 3)
    tau = group_delay(Hs)
    # correction : avancer le grave d'une part du retard lisse, dans la bande, raccord doux
    w = np.zeros(len(f))
    band = (f >= 25) & (f <= FMAX)
    w[band] = 1
    taper = (f > FMAX) & (f < 2 * FMAX)
    w[taper] = 0.5 * (1 + np.cos(np.pi * np.log(f[taper] / FMAX) / np.log(2)))
    low = (f > 15) & (f < 25)
    w[low] = 0.5 * (1 - np.cos(np.pi * (f[low] - 15) / 10))
    tau_c = -PART * np.clip(tau, 0, D * 0.8) * w                  # on n'avance que ce qui est en retard
    phi = -2 * np.pi * np.concatenate([[0], np.cumsum(0.5 * (tau_c[1:] + tau_c[:-1]) * np.diff(f))])
    phi = phi - phi[np.searchsorted(f, 2.2 * FMAX)]          # aigu intact : phase nulle au-dessus de la bande
    Hc = np.exp(1j * phi) * np.exp(-1j * 2 * np.pi * f * D)
    h = np.fft.irfft(Hc, N)[:TAPS]
    fade = int(TAPS * 0.1)
    h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    firs[ch] = h
    # contenu du FIR avant le pic principal (pre-echo) : energie relative
    pk = int(D * FS)
    pre = np.sum(h[:pk - int(0.003 * FS)] ** 2) / np.sum(h ** 2)
    report[ch] = (tau, pre)

# prediction : reponses avec FIR, ramenees au temps d'origine (retard global retire)
new = {}
for ch in ("L", "R"):
    n2 = 1 << (len(irs[ch]) + TAPS).bit_length()
    y = np.fft.irfft(np.fft.rfft(irs[ch], n2) * np.fft.rfft(firs[ch], n2), n2)
    d = int(round(D * FS))
    new[ch] = y[d:d + len(irs[ch])]

print(f"FIR : part {PART}, bande 25-{FMAX:.0f} Hz, retard global {D_MS:.0f} ms, {TAPS} coefficients "
      f"({TAPS / FS * 1000:.0f} ms)")
print("Retard de groupe lisse (ms, relatif a l'aigu) :")
print("    Hz     G avant    D avant")
for x in (30, 40, 50, 60, 70, 80, 100, 125, 160, 200, 300, 500, 1000):
    i = int(np.argmin(np.abs(f - x)))
    print(f"  {x:5d}   {report['L'][0][i] * 1000:8.1f}   {report['R'][0][i] * 1000:8.1f}")
print(f"Energie avant le pic du FIR (pre-echo) : G {100 * report['L'][1]:.1f} %, D {100 * report['R'][1]:.1f} %")
ir2.summary(irs, label + " (mesure, sans FIR)")
ir2.summary(new, "prediction avec FIR")

if "--ecrire" in a:
    d = "/home/rulio12/camilladsp/fir"
    os.makedirs(d, exist_ok=True)
    for ch in ("L", "R"):
        firs[ch].astype("<f4").tofile(os.path.join(d, f"phase_{ch}.raw"))
    print("ecrit :", d)
