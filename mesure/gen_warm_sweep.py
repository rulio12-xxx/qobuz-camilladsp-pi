import numpy as np
from sweep_dsp import generate_log_sweep, write_wav

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
SWEEP_DUR = 8.0
WARMUP_S = 7.5  # marge pour laisser CamillaDSP repasser de STARTING a RUNNING

sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
warmup = np.zeros(int(WARMUP_S * FS))

def write_isolated(path, mono, channel):
    full = np.concatenate([warmup, mono])
    n = len(full)
    stereo = np.zeros((n, 2))
    stereo[:, channel] = full
    write_wav(path, stereo, FS, channels=2, sampwidth=3)

write_isolated(f"{MUSIC_DIR}/warm_sweep_L.wav", sweep, 0)
write_isolated(f"{MUSIC_DIR}/warm_sweep_R.wav", sweep, 1)
print(f"OK : {WARMUP_S}s de silence + {SWEEP_DUR}s de sweep, par voie")
