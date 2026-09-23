#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matrice de mesures : chaque voie (L/R) isolee x plusieurs niveaux de
volume, reponse en frequence (sweep) + THD+N grave (20-200Hz, zone de
l'event) a chaque combinaison. Objectif : verifier si l'event est bien
dimensionne (bruit de turbulence disproportionne aux niveaux forts) et
voir si le mode ~50Hz vient d'une voie en particulier.

Securite : attend 20s avant de commencer (le temps de sortir de la
piece), teste du plus faible au plus fort, et remet un volume raisonnable
a la fin avant de repasser en lecture normale (TSF Jazz).
"""
import json
import subprocess
import time

import numpy as np

from sweep_dsp import (generate_log_sweep, write_wav, read_wav_mono,
                        deconvolve, band_average_db, analyze_tone, find_offset)

MUSIC_DIR = "/home/rulio12/musique"
RESULTS_DIR = "/home/rulio12/bassmeasure/matrix_results"
FS = 44100
DEVICE = "hw:3,0"
MIC_CHANNEL = 0  # Scarlett entree 1

SWEEP_DUR = 8.0
TONE_F1, TONE_F2, PPO, TONE_DUR = 20.0, 200.0, 12, 1.0
FADE_S, GAP_S = 0.015, 0.25
MARKER_F1, MARKER_F2, MARKER_DUR = 500.0, 3000.0, 0.2

LEVELS_DB = [-40, -25, -15, -5, 0]
CHANNELS = {"L": 0, "R": 1}
RESTORE_VOLUME_DB = -35.0
TSF_JAZZ_URL = "http://broadcast.infomaniak.ch/tsfjazz-high.mp3"
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"


def set_main_volume(db):
    code = ("from camilladsp import CamillaClient\n"
            "c = CamillaClient('127.0.0.1', 1234)\n"
            "c.connect()\n"
            f"c.volume.set_main_volume({db})\n")
    subprocess.run([VENV_PY, "-c", code], capture_output=True, timeout=5)

FREQ_BANDS = [20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
              500, 630, 800, 1000, 2000, 5000]


def mpc(*args):
    return subprocess.run(["mpc", *args], capture_output=True, text=True).stdout


def write_isolated(path, mono, channel, fs):
    n = len(mono)
    stereo = np.zeros((n, 2))
    stereo[:, channel] = mono
    write_wav(path, stereo, fs, channels=2, sampwidth=3)


def build_files():
    sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    for name, ch in CHANNELS.items():
        write_isolated(f"{MUSIC_DIR}/mx_sweep_{name}.wav", sweep, ch, FS)

    n_tones = int(np.floor(PPO * np.log2(TONE_F2 / TONE_F1))) + 1
    freqs = [TONE_F1 * (2 ** (i / PPO)) for i in range(n_tones)]

    marker = generate_log_sweep(MARKER_F1, MARKER_F2, MARKER_DUR, FS) * 0.5
    gap = np.zeros(int(GAP_S * FS))
    fade_n = max(1, int(FADE_S * FS))

    chunks = [marker, gap]
    manifest = []
    cursor = len(marker) + len(gap)
    for f in freqs:
        n = int(TONE_DUR * FS)
        t = np.arange(n) / FS
        tone = 0.5 * np.sin(2 * np.pi * f * t)
        fade = np.linspace(0.0, 1.0, fade_n)
        tone[:fade_n] *= fade
        tone[-fade_n:] *= fade[::-1]
        manifest.append({"freq": f, "steady_start_sample": cursor + fade_n,
                          "steady_len_samples": n - 2 * fade_n})
        chunks.append(tone)
        chunks.append(gap)
        cursor += n + len(gap)

    full_mono = np.concatenate(chunks)
    for name, ch in CHANNELS.items():
        write_isolated(f"{MUSIC_DIR}/mx_tones_{name}.wav", full_mono, ch, FS)

    total_s = len(full_mono) / FS
    return freqs, manifest, total_s


def record(seconds, out_path):
    p = subprocess.Popen([
        "arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
        "-c", "2", "-d", str(int(seconds) + 1), out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p


def measure_sweep(channel_name, level_db, sweep_ref):
    fname = f"mx_sweep_{channel_name}.wav"
    rec_path = "/tmp/mx_rec_sweep.wav"
    mpc("clear"); mpc("add", fname)
    rec_proc = record(SWEEP_DUR + 3, rec_path)
    time.sleep(0.4)
    mpc("play")
    rec_proc.wait()
    mpc("stop")

    recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    freqs, mag_db = deconvolve(sweep_ref, recorded, FS)
    bands = band_average_db(freqs, mag_db, FREQ_BANDS)
    ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
    ref = sum(ref_vals) / len(ref_vals) if ref_vals else 0.0
    peak_dbfs = 20 * np.log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    return {"bands_rel_db": {f: (v - ref if v is not None else None) for f, v in bands.items()},
            "peak_dbfs": peak_dbfs}


def measure_thd(channel_name, level_db, manifest, total_s):
    fname = f"mx_tones_{channel_name}.wav"
    rec_path = "/tmp/mx_rec_tones.wav"
    mpc("clear"); mpc("add", fname)
    rec_proc = record(total_s + 3, rec_path)
    time.sleep(0.4)
    mpc("play")
    rec_proc.wait()
    mpc("stop")

    recorded, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    marker = generate_log_sweep(MARKER_F1, MARKER_F2, MARKER_DUR, FS) * 0.5
    offset = find_offset(recorded, marker, search_seconds=10.0, fs=FS)

    results = []
    for t in manifest:
        start = offset + t["steady_start_sample"]
        length = t["steady_len_samples"]
        if start < 0 or start + length > len(recorded):
            continue
        seg = recorded[start:start + length]
        results.append(analyze_tone(seg, FS, t["freq"]))
    return results


def main():
    print("Generation des fichiers de test...")
    freqs, manifest, tones_total_s = build_files()
    print(f"  sweep {SWEEP_DUR}s, {len(freqs)} tons THD ({tones_total_s:.0f}s)")
    subprocess.run(["mpc", "update", "--wait"], check=False)

    print("\n20 secondes pour sortir de la piece...")
    for i in range(20, 0, -5):
        print(f"  {i}s...")
        time.sleep(5)

    print("Amorcage de la route Fichiers -> CamillaDSP...")
    mpc("clear"); mpc("add", f"mx_sweep_L.wav"); mpc("play")
    time.sleep(3.5)
    mpc("stop")
    time.sleep(0.5)

    sweep_ref = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    all_results = {}

    for level in LEVELS_DB:
        print(f"\n=== Niveau {level:+.0f} dB ===")
        set_main_volume(float(level))
        time.sleep(0.3)
        for chname in CHANNELS:
            print(f"  Voie {chname} : sweep...")
            sw = measure_sweep(chname, level, sweep_ref)
            print(f"  Voie {chname} : THD+N grave ({len(freqs)} tons)...")
            thd = measure_thd(chname, level, manifest, tones_total_s)
            all_results[f"{level}_{chname}"] = {"level_db": level, "channel": chname,
                                                 "sweep": sw, "thd": thd}
            worst = max(thd, key=lambda r: r["thdn_pct"]) if thd else None
            print(f"    peak enreg {sw['peak_dbfs']:+.1f} dBFS"
                  + (f" | pire THD+N {worst['thdn_pct']:.2f}% a {worst['f0_nominal']:.0f}Hz" if worst else ""))

    print("\nRestauration du volume et retour a la musique...")
    set_main_volume(RESTORE_VOLUME_DB)

    with open(f"{RESULTS_DIR}/matrix_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Resultats complets : {RESULTS_DIR}/matrix_results.json")

    subprocess.run(["curl", "-s", f"http://127.0.0.1:8080/play?url={TSF_JAZZ_URL}"],
                   capture_output=True)
    print("TSF Jazz lance.")


if __name__ == "__main__":
    main()
