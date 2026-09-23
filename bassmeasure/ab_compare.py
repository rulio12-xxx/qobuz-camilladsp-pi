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


def load_config(path):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.config.set_file_path('{path}')\n"
            "c.general.reload()\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)


def measure(channel_name, tag):
    fname = f"mx_sweep_{channel_name}.wav"
    rec_path = f"/tmp/ab_{tag}_{channel_name}.wav"
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


results = {}
for tag, path in (("PLAIN", "/home/rulio12/camilladsp/configs/camilladsp-fichiers.yml"),
                   ("KICK", "/home/rulio12/camilladsp/configs/camilladsp-fichiers-kick.yml")):
    print(f"\n--- Chargement {tag} ---")
    load_config(path)
    time.sleep(0.5)
    for ch in ("L", "R"):
        results[(tag, ch)] = measure(ch, tag)

print(f"\n{'Hz':>6}  {'L plain':>8}  {'L kick':>8}  {'delta L':>8}   "
      f"{'R plain':>8}  {'R kick':>8}  {'delta R':>8}")
for f in BANDS:
    lp, lk = results[("PLAIN", "L")][f], results[("KICK", "L")][f]
    rp, rk = results[("PLAIN", "R")][f], results[("KICK", "R")][f]
    print(f"{f:>6}  {lp:>+8.1f}  {lk:>+8.1f}  {lk-lp:>+8.1f}   "
          f"{rp:>+8.1f}  {rk:>+8.1f}  {rk-rp:>+8.1f}")
