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
BANDS = [40, 50, 63, 80, 100, 125, 160, 200, 500, 1000]
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def set_main_volume(db):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.volume.set_main_volume({db})\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)


def measure(channel_name):
    fname = f"warm_sweep_{channel_name}.wav"
    rec_path = f"/tmp/deeper50v2_{channel_name}.wav"
    mpc("clear"); mpc("add", fname)
    mpc("play")
    time.sleep(WARMUP_S)  # laisser passer le silence de mise en route

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
    ref = sum(ref_vals) / len(ref_vals)
    peak = 20*np.log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    return {f: (v - ref) for f, v in bands.items()}, peak


print("Amorcage (voie L, avec marge de stabilisation)...")
mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
mpc("stop")
time.sleep(0.5)

set_main_volume(-15.0)
time.sleep(0.3)

print("Mesure voie L...")
L, peakL = measure("L")
print(f"  peak enregistre : {peakL:+.1f} dBFS")
print("Mesure voie R...")
R, peakR = measure("R")
print(f"  peak enregistre : {peakR:+.1f} dBFS")

PREV_L = {40:6.0,50:7.2,63:5.7,80:1.2,100:2.0,125:-0.3,160:2.5,200:2.0,500:0.7,1000:-2.7}
PREV_R = {40:0.6,50:5.7,63:1.0,80:-0.1,100:3.1,125:3.4,160:-1.1,200:1.2,500:-0.1,1000:-1.0}

print("\n(L : compare a la mesure au palier -5dB, donc delta = effet cumule des 2 baisses)")
print(f"{'Hz':>6}  {'L avant':>8}  {'L maint.':>9}  {'deltaL':>7}   {'R avant':>8}  {'R maint.':>9}  {'deltaR':>7}")
for f in BANDS:
    lp, lm = PREV_L[f], L[f]
    rp, rm = PREV_R[f], R[f]
    print(f"{f:>6}  {lp:>+8.1f}  {lm:>+9.1f}  {lm-lp:>+7.2f}   {rp:>+8.1f}  {rm:>+9.1f}  {rm-rp:>+7.2f}")
