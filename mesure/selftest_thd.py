#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-test SANS materiel de analyze_tone() et find_offset() :
synthetise un ton avec une distorsion harmonique CONNUE (1% de 2e
harmonique, 0.5% de 3e) + bruit, et verifie que la mesure retrouve les
bons chiffres. Valide aussi la synchronisation par correlation."""
import numpy as np

from sweep_dsp import analyze_tone, find_offset, generate_log_sweep

FS = 44100
F0 = 1000.0
DURATION = 1.0
H2_RATIO = 0.01   # 1 %
H3_RATIO = 0.005  # 0.5 %
NOISE_RMS = 0.0003

rng = np.random.default_rng(1)
n = int(DURATION * FS)
t = np.arange(n) / FS

signal = (np.sin(2 * np.pi * F0 * t)
          + H2_RATIO * np.sin(2 * np.pi * 2 * F0 * t)
          + H3_RATIO * np.sin(2 * np.pi * 3 * F0 * t))
signal += rng.normal(0, NOISE_RMS, size=n)

res = analyze_tone(signal, FS, F0)

expected_thd_pct = 100 * np.sqrt(H2_RATIO ** 2 + H3_RATIO ** 2)

print("=== Test analyze_tone() ===")
print(f"f0 detectee     : {res['f0_detected']:.2f} Hz (attendu {F0} Hz)")
print(f"THD mesure      : {res['thd_pct']:.4f} % (attendu ~{expected_thd_pct:.4f} %)")
print(f"THD+N mesure    : {res['thdn_pct']:.4f} %")
print(f"Bruit mesure    : {res['noise_dbfs']:+.1f} dBFS")

ok_f0 = abs(res["f0_detected"] - F0) < 1.0
ok_thd = abs(res["thd_pct"] - expected_thd_pct) < 0.05
print(f"\n-> f0 {'OK' if ok_f0 else 'ECART'} / THD {'OK' if ok_thd else 'ECART'}")

print("\n=== Test find_offset() ===")
marker = generate_log_sweep(500, 3000, 0.2, FS) * 0.5
true_offset = 12345
padding = np.zeros(true_offset)
fake_recording = np.concatenate([padding, marker, np.zeros(FS)])
fake_recording += rng.normal(0, 1e-4, size=fake_recording.shape)

detected = find_offset(fake_recording, marker, search_seconds=5.0, fs=FS)
print(f"Decalage reel   : {true_offset}")
print(f"Decalage detecte: {detected}")
print(f"-> {'OK' if detected == true_offset else 'ECART'}")
