import numpy as np
from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve_complex, group_delay_at

FS = 44100
SWEEP_DUR = 8.0
MIC_CHANNEL = 0
N_ITER = 4
CONDITIONS = ["R", "L", "RL"]
DELAY_FREQS = [470, 5000, 10000]

sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)

all_delays = {c: {f: [] for f in DELAY_FREQS} for c in CONDITIONS}

for it in range(1, N_ITER + 1):
    for cond in CONDITIONS:
        rec_path = f"/tmp/it_{it}_{cond}.wav"
        recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
        freqs, H = deconvolve_complex(sweep, recorded, FS)
        delays = group_delay_at(freqs, H, DELAY_FREQS)
        for f in DELAY_FREQS:
            if delays[f] is not None:
                all_delays[cond][f].append(delays[f])

print(f"{'Hz':>6}  {'R (ms)':>10}  {'L (ms)':>10}  {'RL (ms)':>10}  {'R-L (ms)':>10}")
for f in DELAY_FREQS:
    r_vals = all_delays["R"][f]
    l_vals = all_delays["L"][f]
    rl_vals = all_delays["RL"][f]
    r_mean = np.mean(r_vals) if r_vals else None
    l_mean = np.mean(l_vals) if l_vals else None
    rl_mean = np.mean(rl_vals) if rl_vals else None
    r_std = np.std(r_vals) if r_vals else None
    l_std = np.std(l_vals) if l_vals else None
    diff = (r_mean - l_mean) if (r_mean is not None and l_mean is not None) else None

    def fmt(v):
        return f"{v:>10.3f}" if v is not None else f"{'--':>10}"

    print(f"{f:>6}  {fmt(r_mean)}  {fmt(l_mean)}  {fmt(rl_mean)}  {fmt(diff)}")
    print(f"{'':>6}  (std {r_std:.3f})  (std {l_std:.3f})")
