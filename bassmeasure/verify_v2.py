import subprocess
import time
import numpy as np
from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve, band_average_db

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
SWEEP_DUR = 8.0
DEVICE = "hw:3,0"
MIC_CHANNEL = 0
BANDS = [40, 50, 63, 80, 100, 125, 160, 200, 500, 1000]


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def measure(channel_name):
    fname = f"mx_sweep_{channel_name}.wav"
    rec_path = f"/tmp/verify_{channel_name}.wav"
    mpc("clear"); mpc("add", fname)
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                          "-c", "2", "-d", str(int(SWEEP_DUR) + 4), rec_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    mpc("play")
    p.wait()
    mpc("stop")

    sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    freqs, mag_db = deconvolve(sweep, recorded, FS)
    bands = band_average_db(freqs, mag_db, BANDS)
    ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
    ref = sum(ref_vals) / len(ref_vals)
    return {f: (v - ref) for f, v in bands.items()}


print("Amorcage...")
mpc("clear"); mpc("add", "mx_sweep_L.wav"); mpc("play")
time.sleep(3.5)
mpc("stop")
time.sleep(0.5)

for ch in ("L", "R"):
    print(f"\nVoie {ch} :")
    res = measure(ch)
    for f, v in res.items():
        print(f"  {f:>5}Hz  {v:+5.1f} dB")
