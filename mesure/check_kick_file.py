from sweep_dsp import read_wav_mono
import numpy as np

sig, fs = read_wav_mono("/home/rulio12/musique/kick_test.wav", channel=0)
print(f"fs={fs}, len={len(sig)}, dur={len(sig)/fs:.2f}s")
print(f"peak={np.max(np.abs(sig)):.4f}")
win = int(0.05*fs)
n = len(sig)//win
rms = np.sqrt(np.mean(sig[:n*win].reshape(n,win)**2, axis=1))
rms_db = 20*np.log10(np.maximum(rms,1e-9))
for i in range(140,165):
    print(f"{i*win/fs:6.2f}s {rms_db[i]:+6.1f}dB")
