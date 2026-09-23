#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-test de sweep_dsp.py SANS materiel : simule un filtre connu
(coupure grave a 80Hz + bosse a 60Hz) applique numeriquement au sweep,
puis verifie que la deconvolution retrouve bien ce filtre. Valide la
methode avant de faire une vraie mesure au micro."""

import numpy as np
from sweep_dsp import generate_log_sweep, deconvolve, band_average_db

FS = 44100

sweep = generate_log_sweep(f1=20, f2=20000, duration=5.0, fs=FS)

# --- filtre synthetique connu : coupure grave (highpass 2e ordre a 80Hz)
#     + bosse de resonance a 60Hz (+6dB, Q=3) -----------------------------
def biquad_highpass(f0, q, fs):
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * q)
    cosw0 = np.cos(w0)
    b0 = (1 + cosw0) / 2
    b1 = -(1 + cosw0)
    b2 = (1 + cosw0) / 2
    a0 = 1 + alpha
    a1 = -2 * cosw0
    a2 = 1 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1, a1 / a0, a2 / a0])


def biquad_peaking(f0, gain_db, q, fs):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * q)
    cosw0 = np.cos(w0)
    b0 = 1 + alpha * A
    b1 = -2 * cosw0
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cosw0
    a2 = 1 - alpha / A
    return np.array([b0, b1, b2]) / a0, np.array([1, a1 / a0, a2 / a0])


def apply_biquad(x, b, a):
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, xi in enumerate(x):
        yi = b[0] * xi + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        y[i] = yi
        x2, x1 = x1, xi
        y2, y1 = y1, yi
    return y


b1, a1 = biquad_highpass(80, 0.707, FS)
b2, a2 = biquad_peaking(60, 6.0, 3.0, FS)

simulated_recording = apply_biquad(apply_biquad(sweep, b1, a1), b2, a2)
# petit retard + bruit, comme une vraie chaine acoustique
delay_samples = 733
simulated_recording = np.concatenate([np.zeros(delay_samples), simulated_recording])
simulated_recording += np.random.default_rng(0).normal(0, 1e-4, size=simulated_recording.shape)

freqs, mag_db = deconvolve(sweep, simulated_recording, FS)

centers = [20, 30, 40, 50, 60, 63, 80, 100, 125, 160, 200, 500, 1000, 5000]
bands = band_average_db(freqs, mag_db, centers)

print("Frequence(Hz)   Gain mesure (dB)")
for fc in centers:
    v = bands[fc]
    print(f"{fc:>10.0f}      {v:+6.2f}" if v is not None else f"{fc:>10.0f}      (pas de donnees)")

print()
print("Attendu : forte attenuation en dessous de 80Hz (coupure), pic vers 60Hz,")
print("plat (~0dB) au-dessus de 200Hz. Si le tableau ci-dessus correspond,")
print("la methode de deconvolution est validee.")
