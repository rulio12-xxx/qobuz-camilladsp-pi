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
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def set_main_volume(db):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.volume.set_main_volume({db})\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)


def load_config(path):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.config.set_file_path('{path}')\n"
            "c.general.reload()\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)


def measure(tag):
    rec_path = f"/tmp/r50_{tag}.wav"
    mpc("clear"); mpc("add", "it_sweep_R.wav")
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


print("Chargement config kick (v3, coupe 50Hz sur R)...")
load_config("/home/rulio12/camilladsp/configs/camilladsp-fichiers-kick.yml")
time.sleep(0.5)

print("Amorcage...")
mpc("clear"); mpc("add", "it_sweep_R.wav"); mpc("play")
time.sleep(3.5)
mpc("stop")
time.sleep(0.5)

set_main_volume(-15.0)
time.sleep(0.3)

print("Mesure 1/2 (voie R)...")
r1 = measure("1")
print("Mesure 2/2 (voie R)...")
r2 = measure("2")

print(f"\n{'Hz':>6}  {'mesure1':>8}  {'mesure2':>8}  {'ecart':>7}")
for f in BANDS:
    v1, v2 = r1[f], r2[f]
    print(f"{f:>6}  {v1:>+8.1f}  {v2:>+8.1f}  {v2-v1:>+7.2f}")
