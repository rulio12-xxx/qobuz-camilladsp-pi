import numpy as np
from sweep_dsp import read_wav_mono

FS = 44100
recorded, _ = read_wav_mono("/tmp/kick_rec.wav", channel=0)
win = int(0.05 * FS)
n = len(recorded) // win
rms = np.sqrt(np.mean(recorded[: n * win].reshape(n, win) ** 2, axis=1))
rms_db = 20 * np.log10(np.maximum(rms, 1e-9))

print(f"Duree enregistree : {len(recorded)/FS:.2f}s")
for i in range(n):
    t = i * win / FS
    bar = "#" * int(max(0, (rms_db[i] + 60) / 2))
    print(f"{t:6.2f}s  {rms_db[i]:+6.1f}dB  {bar}")
