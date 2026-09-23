import numpy as np
from sweep_dsp import generate_log_sweep, deconvolve_complex, group_delay_at

FS = 44100
sweep = generate_log_sweep(20, 20000, 5.0, FS)

DELAY_SAMPLES = 100
expected_ms = DELAY_SAMPLES / FS * 1000.0

recorded = np.concatenate([np.zeros(DELAY_SAMPLES), sweep, np.zeros(FS)])
recorded += np.random.default_rng(0).normal(0, 1e-5, size=recorded.shape)

freqs, H = deconvolve_complex(sweep, recorded, FS)
delays = group_delay_at(freqs, H, [470, 5000, 10000])

print(f"Retard attendu : {expected_ms:.4f} ms")
for f, d in delays.items():
    print(f"  {f}Hz : {d:.4f} ms  (ecart {d - expected_ms:+.4f} ms)")
