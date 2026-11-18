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

FINE_BANDS = list(range(20, 161, 2))


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def measure(channel_name):
    fname = f"warm_sweep_{channel_name}.wav"
    rec_path = f"/tmp/res_{channel_name}.wav"
    mpc("clear"); mpc("add", fname); mpc("play")
    time.sleep(WARMUP_S)
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                          "-c", "2", "-d", str(int(SWEEP_DUR) + 3), rec_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.wait()
    mpc("stop")

    sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    peak = 20 * np.log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    freqs, mag_db = deconvolve(sweep, recorded, FS)
    bands = band_average_db(freqs, mag_db, FINE_BANDS, frac_octave=1/12)
    ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
    return bands, peak


print("Amorcage...")
mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
mpc("stop")
time.sleep(0.5)

print("Mesure voie L (niveau fort)...")
bandsL, peakL = measure("L")
print(f"  peak {peakL:+.1f} dBFS")
print("Mesure voie R (niveau fort)...")
bandsR, peakR = measure("R")
print(f"  peak {peakR:+.1f} dBFS")

vals_L = np.array([bandsL[f] for f in FINE_BANDS])
vals_R = np.array([bandsR[f] for f in FINE_BANDS])

# Q locale : pic / voisins a +-1 octave approx (ici +-20Hz) pour reperer un pic etroit anormal
print(f"\n{'Hz':>5}  {'L':>7}  {'R':>7}")
for i, f in enumerate(FINE_BANDS):
    print(f"{f:>5}  {vals_L[i]:>+6.1f}  {vals_R[i]:>+6.1f}")

iL = np.argmax(vals_L)
iR = np.argmax(vals_R)
print(f"\nPic max L : {vals_L[iL]:+.1f}dB a {FINE_BANDS[iL]}Hz")
print(f"Pic max R : {vals_R[iR]:+.1f}dB a {FINE_BANDS[iR]}Hz")
