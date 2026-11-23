"""Plafonne le FIR sans kick au niveau du medium sous 38 Hz (rampe 38-44 Hz), phase minimale (23/11/2026).
Demande de Rulio12 : aucun renfort sous 38 Hz. Ancien fichier garde en final/fir_{L,R}_sanskick_avant38.raw.

    python3 correction/convolution/cap38.py && python3 correction/convolution/kick_bas.py --aigu-seul
"""
import os, shutil
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); FS = 44100; NN = 1 << 17
ff = np.fft.rfftfreq(NN, 1 / FS)
for ch in "LR":
    p = os.path.join(D, "final", f"fir_{ch}_sanskick.raw"); keep = p.replace(".raw", "_avant38.raw")
    if not os.path.exists(keep): shutil.copy(p, keep)
    h = np.fromfile(keep, "<f4").astype(float); n = len(h)
    G = 20 * np.log10(np.abs(np.fft.rfft(h, NN)) + 1e-12); med = np.mean(G[(ff >= 400) & (ff <= 1000)])
    cap = np.where(ff < 38, med, np.where(ff < 44, med + (G.max() - med) * (ff - 38) / 6, np.inf))
    G2 = np.minimum(G, cap)
    c = np.fft.irfft(np.log(10 ** (G2 / 20)), NN); w = np.zeros(NN); w[0] = 1; w[1:NN // 2] = 2; w[NN // 2] = 1
    h2 = np.fft.irfft(np.exp(np.fft.rfft(c * w, NN)), NN)[:n]
    fade = n // 8; h2[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    h2.astype("<f4").tofile(p)
    G3 = 20 * np.log10(np.abs(np.fft.rfft(h2, NN)) + 1e-12); d = G3 - G
    print(ch, "sous 38 Hz vs medium max avant", round(float((G[(ff > 20) & (ff < 38)] - med).max()), 1), "apres", round(float((G3[(ff > 20) & (ff < 38)] - med).max()), 1),
          "| ecart 44-20k max", round(float(np.abs(d[(ff > 44) & (ff < 20000)]).max()), 2))
