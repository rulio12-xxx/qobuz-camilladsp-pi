import sys
import subprocess
import time
import numpy as np
from sweep_dsp import write_wav

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
F1 = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
F2 = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
STEP = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
TONE_DUR = float(sys.argv[4]) if len(sys.argv) > 4 else 2.5
GAP_DUR = 0.3
AMPLITUDE = 0.7

freqs = list(np.arange(F1, F2 + STEP/2, STEP))
fade_n = int(0.04 * FS)
fade = np.linspace(0.0, 1.0, fade_n)
gap = np.zeros(int(GAP_DUR * FS))

chunks = []
schedule = []
cursor_s = 0.0
for f in freqs:
    n = int(TONE_DUR * FS)
    t = np.arange(n) / FS
    tone = AMPLITUDE * np.sin(2 * np.pi * f * t)
    tone[:fade_n] *= fade
    tone[-fade_n:] *= fade[::-1]
    schedule.append((cursor_s, f))
    chunks.append(tone)
    chunks.append(gap)
    cursor_s += TONE_DUR + GAP_DUR

full = np.concatenate(chunks)
path = f"{MUSIC_DIR}/tone_sweep_range.wav"
write_wav(path, full, FS, channels=2, sampwidth=3)
subprocess.run(["mpc", "update", "--wait"], check=False)

print(f"Balayage {F1}-{F2}Hz par pas de {STEP}Hz, {TONE_DUR}s chacun ({len(freqs)} tons, "
      f"{cursor_s:.0f}s au total) :")
for t0, f in schedule:
    print(f"  t={t0:5.1f}s -> {f:.1f} Hz")

subprocess.run(["mpc", "clear"], capture_output=True)
subprocess.run(["mpc", "add", "tone_sweep_range.wav"], capture_output=True)
subprocess.run(["mpc", "play"], capture_output=True)
print("\nLecture en cours...")
time.sleep(cursor_s + 1.0)
subprocess.run(["mpc", "stop"], capture_output=True)
print("Termine.")
