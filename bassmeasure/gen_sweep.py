#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genere le sweep de mesure et le place dans la bibliotheque MPD."""
import argparse
import subprocess

from sweep_dsp import generate_log_sweep, write_wav

MUSIC_DIR = "/home/rulio12/musique"
FILENAME = "mesure_sweep.wav"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1", type=float, default=20.0)
    ap.add_argument("--f2", type=float, default=20000.0)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--fs", type=int, default=44100)
    args = ap.parse_args()

    sweep = generate_log_sweep(args.f1, args.f2, args.duration, args.fs)
    path = f"{MUSIC_DIR}/{FILENAME}"
    write_wav(path, sweep, args.fs, channels=2, sampwidth=3)
    print(f"Sweep genere : {path} ({args.f1}-{args.f2} Hz, {args.duration}s, {args.fs}Hz/24bit)")

    subprocess.run(["mpc", "update", "--wait"], check=False)
    print("Bibliotheque MPD mise a jour.")


if __name__ == "__main__":
    main()
