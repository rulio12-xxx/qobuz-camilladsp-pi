#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4 iterations identiques (R, L, R+L) a -15dB, pour :
  1. comprendre la variabilite mesure-a-mesure (repetabilite) - explique
     si la derive vue precedemment est reelle (pièce/micro) ou du bruit
     de mesure ;
  2. verifier le delai de reponse (groupe) entre R, L et R+L a 470Hz,
     5kHz et 10kHz (alignement temporel).

Config CamillaDSP laissee telle quelle (pas de rechargement) : on isole
la variable mesure, pas la variable EQ.
"""
import subprocess
import time
import json

import numpy as np
from sweep_dsp import (generate_log_sweep, write_wav, read_wav_mono,
                        deconvolve, deconvolve_complex, group_delay_at,
                        band_average_db)

MUSIC_DIR = "/home/rulio12/musique"
FS = 44100
SWEEP_DUR = 8.0
DEVICE = "hw:3,0"
MIC_CHANNEL = 0
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"

LEVEL_DB = -15.0
N_ITER = 4
CONDITIONS = ["R", "L", "RL"]
DELAY_FREQS = [470, 5000, 10000]
BANDS = [40, 50, 63, 80, 100, 125, 160, 200, 500, 1000]

RESULTS_PATH = "/home/rulio12/bassmeasure/iterate_delay_results.json"


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def set_main_volume(db):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.volume.set_main_volume({db})\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)


def write_isolated(path, mono, channel, fs):
    n = len(mono)
    stereo = np.zeros((n, 2))
    if channel is None:  # R+L
        stereo[:, 0] = mono
        stereo[:, 1] = mono
    else:
        stereo[:, channel] = mono
    write_wav(path, stereo, fs, channels=2, sampwidth=3)


def build_files():
    sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    write_isolated(f"{MUSIC_DIR}/it_sweep_R.wav", sweep, 1, FS)
    write_isolated(f"{MUSIC_DIR}/it_sweep_L.wav", sweep, 0, FS)
    write_isolated(f"{MUSIC_DIR}/it_sweep_RL.wav", sweep, None, FS)
    subprocess.run(["mpc", "update", "--wait"], check=False)
    return sweep


def measure_one(cond, tag):
    fname = f"it_sweep_{cond}.wav"
    rec_path = f"/tmp/it_{tag}.wav"
    mpc("clear"); mpc("add", fname)
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                          "-c", "2", "-d", str(int(SWEEP_DUR) + 4), rec_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    mpc("play")
    p.wait()
    mpc("stop")
    return read_wav_mono(rec_path, channel=MIC_CHANNEL)


def main():
    print("Generation des fichiers isoles...")
    sweep = build_files()

    print("Amorcage...")
    mpc("clear"); mpc("add", "it_sweep_RL.wav"); mpc("play")
    time.sleep(3.5)
    mpc("stop")
    time.sleep(0.5)

    print(f"Reglage du volume a {LEVEL_DB} dB")
    set_main_volume(LEVEL_DB)
    time.sleep(0.3)

    all_results = []

    for it in range(1, N_ITER + 1):
        print(f"\n=== Iteration {it}/{N_ITER} ===")
        iter_data = {}
        for cond in CONDITIONS:
            print(f"  {cond}...")
            recorded, _ = measure_one(cond, f"{it}_{cond}")
            freqs, H = deconvolve_complex(sweep, recorded, FS)
            mag_db = 20 * np.log10(np.maximum(np.abs(H), 1e-12))
            bands = band_average_db(freqs, mag_db, BANDS)
            ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
            ref = sum(ref_vals) / len(ref_vals) if ref_vals else 0.0
            bands_rel = {f: (v - ref if v is not None else None) for f, v in bands.items()}
            delays = group_delay_at(freqs, H, DELAY_FREQS)
            iter_data[cond] = {"bands_rel_db": bands_rel, "delay_ms": delays}
        all_results.append(iter_data)

    with open(RESULTS_PATH, "w") as f:
        json.dump(all_results, f, indent=2)

    # --- rapport repetabilite (variance inter-iterations) ---
    print("\n\n=== Repetabilite (ecart-type sur les 4 iterations, dB) ===")
    print(f"{'Hz':>6}  {'std R':>7}  {'std L':>7}  {'std RL':>7}")
    for f in BANDS:
        stds = []
        for cond in CONDITIONS:
            vals = [all_results[i][cond]["bands_rel_db"][f] for i in range(N_ITER)]
            vals = [v for v in vals if v is not None]
            stds.append(np.std(vals) if len(vals) > 1 else None)
        s = "  ".join(f"{v:>7.2f}" if v is not None else f"{'--':>7}" for v in stds)
        print(f"{f:>6}  {s}")

    # --- rapport delai ---
    print("\n=== Delai de groupe (ms), moyenne des 4 iterations ===")
    print(f"{'Hz':>6}  {'R':>8}  {'L':>8}  {'RL':>8}  {'R-L':>8}")
    for fdel in DELAY_FREQS:
        means = {}
        for cond in CONDITIONS:
            vals = [all_results[i][cond]["delay_ms"][fdel] for i in range(N_ITER)
                    if all_results[i][cond]["delay_ms"][fdel] is not None]
            means[cond] = np.mean(vals) if vals else None
        r, l, rl = means["R"], means["L"], means["RL"]
        rminusl = (r - l) if (r is not None and l is not None) else None
        def fmt(v):
            return f"{v:>8.3f}" if v is not None else f"{'--':>8}"
        print(f"{fdel:>6}  {fmt(r)}  {fmt(l)}  {fmt(rl)}  {fmt(rminusl)}")

    print(f"\nResultats bruts : {RESULTS_PATH}")


if __name__ == "__main__":
    main()
