"""Test (23/11/2026, demande de Rulio12) : bosse principale du grave a +10 dB au-dessus du medium au lieu de +13.
FIR = FIR final x (cible bosse 7,25 / cible bosse 11), reconstruit en phase minimale, sans mesure.
Ecrit final/fir_{L,R}_{sanskick,kick}_b10.raw.

    python3 correction/convolution/bosse10.py            # +10 dB (b10)
    python3 correction/convolution/bosse10.py 4.0 b7    # +7 dB (b7)
    python3 correction/convolution/bosse10.py 4.5 b7f66 70   # +7 dB, sommet 66 Hz au lieu de 56
    python3 correction/convolution/bosse10.py 5.0 b7f76 82   # +7 dB, sommet 76 Hz
"""
import os, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "comparaison")); sys.path.insert(0, D)
from cible import cible_db
FS = 44100; NN = 1 << 17; f = np.fft.rfftfreq(NN, 1 / FS)
BOSSE = float(sys.argv[1]) if len(sys.argv) > 1 else 7.25   # 7,25 -> +10 dB ; 4,0 -> +7 dB
SUF = sys.argv[2] if len(sys.argv) > 2 else "b10"
FB = float(sys.argv[3]) if len(sys.argv) > 3 else 58.0   # frequence de la bosse
ratio = cible_db(f, BOSSE, FB) - cible_db(f, 11.0)
db = lambda h: 20 * np.log10(np.abs(np.fft.rfft(h, NN)) + 1e-12)
for v in ("sanskick", "kick"):
    for ch in "LR":
        h = np.fromfile(os.path.join(D, "final", f"fir_{ch}_{v}.raw"), "<f4").astype(float); n = len(h)
        G = db(h) + ratio
        c = np.fft.irfft(np.log(10 ** (G / 20)), NN); w = np.zeros(NN); w[0] = 1; w[1:NN // 2] = 2; w[NN // 2] = 1
        h2 = np.fft.irfft(np.exp(np.fft.rfft(c * w, NN)), NN)[:n]
        fade = n // 8; h2[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
        h2.astype("<f4").tofile(os.path.join(D, "final", f"fir_{ch}_{v}_{SUF}.raw"))
        d = db(h2) - db(h)
        print(v, ch, [(x, round(float(d[np.argmin(abs(f - x))]), 1)) for x in (30, 40, 50, 58, 70, 100, 150, 200, 500, 5000)],
              "crete", round(float(db(h2)[f < 20000].max()) - 20.5, 1))
