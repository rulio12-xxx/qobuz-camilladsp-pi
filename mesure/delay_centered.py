import subprocess
import time
import numpy as np
from sweep_dsp import generate_log_sweep, read_wav_mono, find_offset

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
SWEEP_DUR = 8.0
WARMUP_S = 7.5
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def record(channel_name, tag):
    fname = f"warm_sweep_{channel_name}.wav"
    rec_path = f"/tmp/centered_{tag}_{channel_name}.wav"
    mpc("clear"); mpc("add", fname); mpc("play")
    time.sleep(WARMUP_S)
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                          "-c", "2", "-d", str(int(SWEEP_DUR) + 3), rec_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.wait()
    mpc("stop")
    sig, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    peak = 20*np.log10(max(abs(sig.max()), abs(sig.min()), 1e-9))
    return sig, peak


print("Amorcage...")
mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
mpc("stop")
time.sleep(0.5)

offsets_ms = []
for i in range(1, 3):
    print(f"\n--- Mesure {i}/2 ---")
    r, peakR = record("R", i)
    print(f"  R : peak {peakR:+.1f} dBFS")
    l, peakL = record("L", i)
    print(f"  L : peak {peakL:+.1f} dBFS")

    # le marqueur doit venir du vrai signal (apres les WARMUP_S de silence),
    # pas du debut de l'enregistrement qui est silencieux
    marker_start = int(WARMUP_S * FS)
    marker_end = marker_start + int(3.0 * FS)
    off_samples = find_offset(l, r[marker_start:marker_end], search_seconds=15.0, fs=FS)
    # off_samples est la position absolue dans L ou le marqueur (extrait a
    # marker_start dans R) est retrouve -> le delai relatif est l'ecart a
    # cette meme position nominale
    relative_samples = off_samples - marker_start
    off_ms = relative_samples / FS * 1000.0
    offsets_ms.append(off_ms)
    print(f"  -> L en retard de {off_ms:+.2f} ms sur R")

print(f"\nMoyenne : {np.mean(offsets_ms):+.2f} ms, ecart-type : {np.std(offsets_ms):.2f} ms")
print("(delay_L actuel dans la config : 1.2ms, delay_R : 0ms)")
