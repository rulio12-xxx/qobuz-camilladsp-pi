import numpy as np
from sweep_dsp import read_wav_mono
from gen_kick import WARMUP_S, N_HITS, HIT_PERIOD_S

FS = 44100
recorded, _ = read_wav_mono("/tmp/kick_rec.wav", channel=0)
print(f"Duree enregistree : {len(recorded)/FS:.2f}s, peak global="
      f"{20*np.log10(max(abs(recorded.max()),abs(recorded.min()),1e-9)):+.1f}dBFS")

win = int(0.01 * FS)
n = len(recorded) // win
rms = np.sqrt(np.mean(recorded[: n * win].reshape(n, win) ** 2, axis=1))
rms_db = 20 * np.log10(np.maximum(rms, 1e-9))

for i in range(N_HITS):
    center = WARMUP_S + i * HIT_PERIOD_S
    lo_i = int((center - 0.2) / (win / FS))
    hi_i = int((center + 0.3) / (win / FS))
    print(f"\n-- coup {i+1}, attendu a {center:.2f}s --")
    for j in range(lo_i, hi_i):
        t = j * win / FS
        bar = "#" * int(max(0, (rms_db[j] + 60) / 2))
        print(f"{t:6.3f}s  {rms_db[j]:+6.1f}dB  {bar}")
