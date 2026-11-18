import numpy as np
from sweep_dsp import read_wav_mono

for ch in ("L", "R"):
    sig, fs = read_wav_mono(f"/tmp/deeper50_{ch}.wav", channel=0)
    peak = max(abs(sig.max()), abs(sig.min()))
    rms = np.sqrt(np.mean(sig**2))
    peak_db = 20*np.log10(max(peak,1e-9))
    rms_db = 20*np.log10(max(rms,1e-9))
    print(f"{ch}: fs={fs}, len={len(sig)} samples ({len(sig)/fs:.1f}s), peak={peak_db:+.1f}dBFS, rms={rms_db:+.1f}dBFS")
