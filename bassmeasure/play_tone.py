import sys
import subprocess
import time
import numpy as np
from sweep_dsp import write_wav

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
FREQ = float(sys.argv[1]) if len(sys.argv) > 1 else 37.0
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
AMPLITUDE = 0.7  # -6dBFS de marge

n = int(DUR * FS)
t = np.arange(n) / FS
tone = AMPLITUDE * np.sin(2 * np.pi * FREQ * t)
fade_n = int(0.05 * FS)
fade = np.linspace(0.0, 1.0, fade_n)
tone[:fade_n] *= fade
tone[-fade_n:] *= fade[::-1]

path = f"{MUSIC_DIR}/tone_test.wav"
write_wav(path, tone, FS, channels=2, sampwidth=3)
subprocess.run(["mpc", "update", "--wait"], check=False)

subprocess.run(["mpc", "clear"], capture_output=True)
subprocess.run(["mpc", "add", "tone_test.wav"], capture_output=True)
subprocess.run(["mpc", "play"], capture_output=True)
print(f"Ton {FREQ}Hz en cours ({DUR}s)...")
time.sleep(DUR + 0.5)
subprocess.run(["mpc", "stop"], capture_output=True)
print("Termine.")
