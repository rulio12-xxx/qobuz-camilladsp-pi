#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genere la sequence de tons purs (grille log, defaut 1/12 octave,
20Hz-20kHz) + un marqueur de synchronisation, pour la mesure THD+N."""
import argparse
import json
import subprocess

import numpy as np

from sweep_dsp import generate_log_sweep, write_wav

MUSIC_DIR = "/home/rulio12/musique"
FILENAME = "mesure_tones.wav"
MANIFEST = "/home/rulio12/bassmeasure/tones_manifest.json"

FADE_S = 0.015
GAP_S = 0.25
MARKER_F1, MARKER_F2, MARKER_DUR = 500.0, 3000.0, 0.2
AMPLITUDE = 0.5  # -6 dBFS de marge


def octave_freqs(f_lo, f_hi, points_per_octave):
    n = int(np.floor(points_per_octave * np.log2(f_hi / f_lo))) + 1
    return [f_lo * (2 ** (i / points_per_octave)) for i in range(n)]


def make_tone(freq, duration, fs, amplitude=AMPLITUDE):
    n = int(duration * fs)
    t = np.arange(n) / fs
    tone = amplitude * np.sin(2 * np.pi * freq * t)
    fade_n = max(1, int(FADE_S * fs))
    fade = np.linspace(0.0, 1.0, fade_n)
    tone[:fade_n] *= fade
    tone[-fade_n:] *= fade[::-1]
    return tone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1", type=float, default=20.0)
    ap.add_argument("--f2", type=float, default=20000.0)
    ap.add_argument("--points-per-octave", type=int, default=12)
    ap.add_argument("--tone-duration", type=float, default=1.0)
    ap.add_argument("--fs", type=int, default=44100)
    args = ap.parse_args()

    fs = args.fs
    freqs = octave_freqs(args.f1, args.f2, args.points_per_octave)
    print(f"{len(freqs)} frequences generees ({args.f1}-{args.f2}Hz, "
          f"1/{args.points_per_octave} octave)")

    marker = generate_log_sweep(MARKER_F1, MARKER_F2, MARKER_DUR, fs) * AMPLITUDE
    gap = np.zeros(int(GAP_S * fs))

    chunks = [marker, gap]
    manifest = {
        "fs": fs,
        "marker_duration": MARKER_DUR,
        "gap": GAP_S,
        "fade": FADE_S,
        "tone_duration": args.tone_duration,
        "tones": [],
    }

    cursor = len(marker) + len(gap)  # position en echantillons depuis le debut
    for f in freqs:
        tone = make_tone(f, args.tone_duration, fs)
        # zone stable = apres le fade-in, avant le fade-out
        fade_n = max(1, int(FADE_S * fs))
        steady_start = cursor + fade_n
        steady_len = len(tone) - 2 * fade_n
        manifest["tones"].append({
            "freq": f,
            "steady_start_sample": int(steady_start),
            "steady_len_samples": int(steady_len),
        })
        chunks.append(tone)
        chunks.append(gap)
        cursor += len(tone) + len(gap)

    full = np.concatenate(chunks)
    path = f"{MUSIC_DIR}/{FILENAME}"
    write_wav(path, full, fs, channels=2, sampwidth=3)

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    total_s = len(full) / fs
    print(f"Fichier : {path} ({total_s:.0f}s, {total_s/60:.1f} min)")
    print(f"Manifest : {MANIFEST}")

    subprocess.run(["mpc", "update", "--wait"], check=False)
    print("Bibliotheque MPD mise a jour.")


if __name__ == "__main__":
    main()
