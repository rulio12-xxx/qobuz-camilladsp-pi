#!/usr/bin/env python3
from sweep_dsp import read_wav_mono, deconvolve, band_average_db

MUSIC_DIR = "/home/rulio12/musique"
FILENAME = "mesure_sweep.wav"
REC_PATH = "/tmp/mesure_rec.wav"

BAND_CENTERS = [20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
                500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
                6300, 8000, 10000, 12500, 16000]

sweep, sweep_fs = read_wav_mono(f"{MUSIC_DIR}/{FILENAME}")
recorded, rec_fs = read_wav_mono(REC_PATH, channel=0)

freqs, mag_db = deconvolve(sweep, recorded, sweep_fs)
bands = band_average_db(freqs, mag_db, BAND_CENTERS)

ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
ref = sum(ref_vals) / len(ref_vals)

print(f"0 dB = moyenne 200-1000Hz ({ref:+.1f} dB brut)\n")
for fc in BAND_CENTERS:
    v = bands[fc]
    if v is None:
        continue
    rel = v - ref
    frac = max(0.0, min(1.0, (rel + 15) / 25))
    n = int(round(frac * 40))
    print(f"{fc:>6}  {rel:+6.1f}  {'#'*n}{'.'*(40-n)}")
