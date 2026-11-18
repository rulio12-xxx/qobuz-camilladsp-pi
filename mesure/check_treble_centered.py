import subprocess
import time
import numpy as np
from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve, band_average_db

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
SWEEP_DUR = 8.0
WARMUP_S = 7.5
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0
BANDS = [500, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000]


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def measure(channel_name):
    fname = f"warm_sweep_{channel_name}.wav"
    rec_path = f"/tmp/treble_{channel_name}.wav"
    mpc("clear"); mpc("add", fname); mpc("play")
    time.sleep(WARMUP_S)
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                          "-c", "2", "-d", str(int(SWEEP_DUR) + 3), rec_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.wait()
    mpc("stop")

    sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    freqs, mag_db = deconvolve(sweep, recorded, FS)
    bands = band_average_db(freqs, mag_db, BANDS)
    ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
    # 200Hz pas dans BANDS ici, on utilise juste 500-1000 comme reference locale
    ref_vals = [bands[500], bands[1000]]
    ref = sum(ref_vals) / len(ref_vals)
    peak = 20*np.log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    return {f: (v - ref) for f, v in bands.items()}, peak


print("Amorcage...")
mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
mpc("stop")
time.sleep(0.5)

print("Mesure voie L...")
L, peakL = measure("L")
print(f"  peak {peakL:+.1f} dBFS")
print("Mesure voie R...")
R, peakR = measure("R")
print(f"  peak {peakR:+.1f} dBFS")

# derniere projection calculee (pas mesuree) pour comparaison, moyenne L/R
PROJECTED = {500:0.30,1000:-1.84,1250:1.31,1600:2.42,2000:2.83,2500:4.35,3150:5.59,
             4000:2.99,5000:-0.70,6300:-0.62,8000:-3.13,10000:-6.48,12500:-5.74,16000:-10.66}

print(f"\n{'Hz':>6}  {'L':>7}  {'R':>7}  {'moy L/R':>8}  {'projete':>8}")
for f in BANDS:
    moy = (L[f] + R[f]) / 2
    print(f"{f:>6}  {L[f]:>+6.1f}  {R[f]:>+6.1f}  {moy:>+7.1f}  {PROJECTED[f]:>+7.1f}")
