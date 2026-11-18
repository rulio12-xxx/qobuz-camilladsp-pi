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
BANDS = [20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000]


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def measure(channel_name):
    fname = f"warm_sweep_{channel_name}.wav"
    rec_path = f"/tmp/bass_{channel_name}.wav"
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
    ref = sum(ref_vals) / len(ref_vals) if ref_vals else 0.0
    peak = 20*np.log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    return {f: (v - ref) for f, v in bands.items()}, peak, ref


print("Amorcage...")
mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
mpc("stop")
time.sleep(0.5)

print("Mesure voie L...")
L, peakL, refL = measure("L")
print(f"  peak {peakL:+.1f} dBFS")
print("Mesure voie R...")
R, peakR, refR = measure("R")
print(f"  peak {peakR:+.1f} dBFS")

print(f"\n{'Hz':>6}  {'L':>7}  {'R':>7}")
for f in BANDS:
    print(f"{f:>6}  {L[f]:>+6.1f}  {R[f]:>+6.1f}")
