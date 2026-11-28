"""--aigu-seul (23/11 soir) : grave identique a la version sans kick, seulement la rehausse du clic
2-10 kHz (Peaking 4,5 kHz +1,5 dB Q1). Sous 38 Hz : FIR plafonne au niveau du medium (aucun renfort), rampe 38-44 Hz.

FIR kick « bas » (23/11/2026) : la bosse du kick reste sous 100 Hz.

Rulio12 trouvait genant le renfort 100-150 Hz du FIR kick. Ici, pas de nouvelle mesure :
FIR kick = FIR sans kick (final/) x Peaking 65 Hz +3,5 dB Q3 (crete totale <= -3 dBFS) x clic 4,5 kHz +1,5 dB Q1.
Exact par rapport a la version sans kick (chaine lineaire) : 100-150 Hz ne bouge plus que de +0,1 a +0,6 dB.

    python3 correction/convolution/kick_bas.py   -> final/fir_{L,R}_kick.raw (anciens gardes en final/fir_{L,R}_kick_78hz.raw)
"""
import os, shutil, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__))
FS = 44100


def biquad_coefs(fc, gain, q):
    A = 10 ** (gain / 40); w = 2 * np.pi * fc / FS; al = np.sin(w) / (2 * q); c = np.cos(w)
    b = np.array([1 + al * A, -2 * c, 1 - al * A]); a = np.array([1 + al / A, -2 * c, 1 - al / A])
    return b / a[0], a / a[0]


def lfilter(b, a, x):
    y = np.zeros_like(x); x1 = x2 = y1 = y2 = 0.0
    for n, xn in enumerate(x):
        yn = b[0] * xn + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1, y2, y1 = x1, xn, y1, yn; y[n] = yn
    return y


import sys as _s
KICK = (65.0, 3.5, 3.0) if "--aigu-seul" not in _s.argv else (65.0, 0.0, 3.0); CLIC = (4500.0, 1.5, 1.0)
for ch in "LR":
    old = os.path.join(D, "final", f"fir_{ch}_kick.raw"); keep = os.path.join(D, "final", f"fir_{ch}_kick_78hz.raw")
    if not os.path.exists(keep): shutil.copy(old, keep)
    h = np.fromfile(os.path.join(D, "final", f"fir_{ch}_sanskick.raw"), "<f4").astype(float)
    for p in (KICK, CLIC): h = lfilter(*biquad_coefs(*p), h)
    fade = len(h) // 8; h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    if "--aigu-seul" in sys.argv:
        # rien au-dessus du niveau du medium sous 38 Hz (rampe 38-44 Hz), reconstruit en phase minimale
        NN = 1 << 17; ff = np.fft.rfftfreq(NN, 1 / FS); G = 20 * np.log10(np.abs(np.fft.rfft(h, NN)) + 1e-12)
        med = np.mean(G[(ff >= 400) & (ff <= 1000)])
        cap = np.where(ff < 38, med, np.where(ff < 44, med + (G.max() - med) * (ff - 38) / 6, np.inf))
        G = np.minimum(G, cap)
        c = np.fft.irfft(np.log(10 ** (G / 20)), NN); w = np.zeros(NN); w[0] = 1; w[1:NN // 2] = 2; w[NN // 2] = 1
        h = np.fft.irfft(np.exp(np.fft.rfft(c * w, NN)), NN)[:len(h)]
        h[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    h.astype("<f4").tofile(old)
    N = 1 << 17; f = np.fft.rfftfreq(N, 1 / FS); db = lambda x: 20 * np.log10(np.abs(np.fft.rfft(x, N)) + 1e-12)
    s = np.fromfile(os.path.join(D, "final", f"fir_{ch}_sanskick.raw"), "<f4").astype(float)
    o = np.fromfile(keep, "<f4").astype(float)
    d_new, d_old = db(h) - db(s), db(o) - db(s)
    pts = (60, 65, 80, 100, 120, 150, 200, 4500)
    print(ch, "nouveau", [(x, round(float(d_new[np.argmin(abs(f - x))]), 1)) for x in pts])
    print(ch, "ancien ", [(x, round(float(d_old[np.argmin(abs(f - x))]), 1)) for x in pts])
    print(ch, "crete dBFS : nouveau", round(float(db(h)[f < 20000].max()), 1), "ancien", round(float(db(o)[f < 20000].max()), 1), "sans kick", round(float(db(s)[f < 20000].max()), 1))
