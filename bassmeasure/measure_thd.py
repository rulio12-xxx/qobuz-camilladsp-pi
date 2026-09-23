#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure THD+N sur toute la bande (grille log de tons purs, cf gen_tones.py).

Meme sequence que measure.py (amorcage source Fichiers, enregistrement
Scarlett 2i2), puis synchronisation precise par correlation avec le
marqueur, et analyse harmonique de chaque ton par FFT fenetree.
"""
import argparse
import json
import subprocess
import time

import numpy as np

from sweep_dsp import read_wav_mono, generate_log_sweep, find_offset, analyze_tone

MUSIC_DIR = "/home/rulio12/musique"
FILENAME = "mesure_tones.wav"
MANIFEST = "/home/rulio12/bassmeasure/tones_manifest.json"
REC_PATH = "/tmp/mesure_thd_rec.wav"

MARKER_F1, MARKER_F2, MARKER_DUR = 500.0, 3000.0, 0.2


def mpc(*args):
    return subprocess.run(["mpc", *args], capture_output=True, text=True).stdout


def bar(db, lo=-100, hi=-20, width=30):
    frac = max(0.0, min(1.0, (db - lo) / (hi - lo)))
    n = int(round(frac * width))
    return "#" * n + "." * (width - n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="hw:3,0")
    ap.add_argument("--tail", type=float, default=3.0)
    ap.add_argument("--rate", type=int, default=44100)
    ap.add_argument("--prime-seconds", type=float, default=3.5)
    ap.add_argument("--channel", type=int, default=0, help="canal du Scarlett ou est le micro (0=entree1)")
    args = ap.parse_args()

    with open(MANIFEST) as f:
        manifest = json.load(f)
    fs = manifest["fs"]
    total_samples = (manifest["tones"][-1]["steady_start_sample"]
                      + manifest["tones"][-1]["steady_len_samples"]
                      + int(manifest["fade"] * fs) + int(manifest["gap"] * fs))
    total_s = total_samples / fs
    print(f"Sequence : {len(manifest['tones'])} tons, {total_s:.0f}s ({total_s/60:.1f} min)")

    print("\n[1/4] Amorcage de la route Fichiers -> CamillaDSP...")
    mpc("clear")
    mpc("add", FILENAME)
    mpc("play")
    time.sleep(args.prime_seconds)
    mpc("stop")
    time.sleep(0.5)

    print("[2/4] Demarrage de l'enregistrement (Scarlett 2i2)...")
    rec_seconds = int(total_s + args.tail) + 1
    rec_proc = subprocess.Popen([
        "arecord", "-D", args.device, "-f", "S32_LE", "-r", str(args.rate),
        "-c", "2", "-d", str(rec_seconds), REC_PATH
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)

    print("[3/4] Lecture de la sequence de tons...")
    mpc("clear")
    mpc("add", FILENAME)
    mpc("play")

    rec_proc.wait()
    mpc("stop")
    print("Enregistrement termine.")

    print("\n[4/4] Analyse...")
    recorded, rec_fs = read_wav_mono(REC_PATH, channel=args.channel)
    if rec_fs != fs:
        print(f"ATTENTION : sample rate different (attendu {fs}, obtenu {rec_fs})")

    marker = generate_log_sweep(MARKER_F1, MARKER_F2, MARKER_DUR, fs) * 0.5
    offset = find_offset(recorded, marker, search_seconds=10.0, fs=fs)
    print(f"Synchronisation : decalage detecte = {offset} echantillons ({offset/fs*1000:.1f} ms)")

    results = []
    for t in manifest["tones"]:
        start = offset + t["steady_start_sample"]
        length = t["steady_len_samples"]
        if start < 0 or start + length > len(recorded):
            continue
        segment = recorded[start:start + length]
        res = analyze_tone(segment, fs, t["freq"])
        results.append(res)

    print(f"\n{'Hz':>8}  {'THD%':>7}  {'THD+N%':>7}  {'THD+N dB':>9}  {'Bruit dBFS':>10}  Niveau THD+N")
    for r in results:
        print(f"{r['f0_nominal']:>8.1f}  {r['thd_pct']:>6.3f}%  {r['thdn_pct']:>6.3f}%  "
              f"{r['thdn_db']:>+8.1f}  {r['noise_dbfs']:>+9.1f}  {bar(r['thdn_db'])}")

    worst = max(results, key=lambda r: r["thdn_pct"])
    print(f"\nPire THD+N : {worst['thdn_pct']:.3f}% ({worst['thdn_db']:+.1f} dB) a {worst['f0_nominal']:.0f} Hz")

    out_path = "/home/rulio12/bassmeasure/last_thd_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Resultats complets : {out_path}")


if __name__ == "__main__":
    main()
