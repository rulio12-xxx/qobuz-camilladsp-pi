#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure la reponse en frequence du systeme complet (MPD -> selecteur ->
CamillaDSP -> DAC -> enceintes -> micro -> Scarlett 2i2) par sweep log +
deconvolution.

Sequence :
  1. amorcage : joue le sweep une premiere fois pour laisser le temps au
     selecteur de basculer sur la config "Fichiers" (~2-3s de debounce) ;
  2. lance l'enregistrement sur le Scarlett 2i2 ;
  3. rejoue le sweep depuis le debut (cette fois-ci deja route correctement) ;
  4. analyse le fichier enregistre par deconvolution.
"""
import argparse
import subprocess
import time

from sweep_dsp import read_wav_mono, deconvolve, band_average_db

MUSIC_DIR = "/home/rulio12/musique"
FILENAME = "mesure_sweep.wav"
REC_PATH = "/tmp/mesure_rec.wav"

BAND_CENTERS = [20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000]


def mpc(*args):
    return subprocess.run(["mpc", *args], capture_output=True, text=True).stdout


def get_sweep_duration_and_fs():
    _, fs = read_wav_mono(f"{MUSIC_DIR}/{FILENAME}")
    import wave
    with wave.open(f"{MUSIC_DIR}/{FILENAME}", "rb") as w:
        n = w.getnframes()
    return n / fs, fs


def bar(db, lo=-30, hi=6, width=40):
    frac = max(0.0, min(1.0, (db - lo) / (hi - lo)))
    n = int(round(frac * width))
    return "#" * n + "." * (width - n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="hw:3,0", help="peripherique ALSA de capture (Scarlett)")
    ap.add_argument("--tail", type=float, default=3.0, help="marge (s) apres la fin du sweep")
    ap.add_argument("--rate", type=int, default=44100)
    ap.add_argument("--channel", type=int, default=0, help="canal du Scarlett ou est le micro (0=entree1)")
    args = ap.parse_args()

    duration, fs = get_sweep_duration_and_fs()
    print(f"Sweep : {duration:.1f}s @ {fs}Hz")

    print("\n[1/4] Amorcage de la route Fichiers -> CamillaDSP...")
    mpc("clear")
    mpc("add", FILENAME)
    mpc("play")
    time.sleep(min(duration, 3.5))
    mpc("stop")
    time.sleep(0.5)

    print("[2/4] Demarrage de l'enregistrement (Scarlett 2i2)...")
    rec_seconds = int(duration + args.tail) + 1
    rec_proc = subprocess.Popen([
        "arecord", "-D", args.device, "-f", "S32_LE", "-r", str(args.rate),
        "-c", "2", "-d", str(rec_seconds), REC_PATH
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)

    print("[3/4] Lecture du sweep...")
    mpc("clear")
    mpc("add", FILENAME)
    mpc("play")

    rec_proc.wait()
    mpc("stop")
    print("Enregistrement termine.")

    print("\n[4/4] Analyse...")
    sweep, sweep_fs = read_wav_mono(f"{MUSIC_DIR}/{FILENAME}")
    recorded, rec_fs = read_wav_mono(REC_PATH, channel=args.channel)

    if sweep_fs != rec_fs:
        print(f"ATTENTION : sample rate different (sweep {sweep_fs}Hz, enreg {rec_fs}Hz) "
              "- resultat potentiellement fausse.")

    peak_dbfs = 20 * __import__("math").log10(max(abs(recorded.max()), abs(recorded.min()), 1e-9))
    print(f"Niveau de pointe enregistre : {peak_dbfs:+.1f} dBFS", end="")
    if peak_dbfs > -3.0:
        print("  !! proche de la saturation du convertisseur - baisser le gain d'entree du Scarlett")
    elif peak_dbfs < -30.0:
        print("  -- signal faible, envisager de monter le gain d'entree du Scarlett")
    else:
        print("  (marge correcte)")

    freqs, mag_db = deconvolve(sweep, recorded, sweep_fs)
    bands = band_average_db(freqs, mag_db, BAND_CENTERS)

    # normalisation : 0 dB = moyenne 200-1000Hz (repere de niveau relatif)
    ref_vals = [v for f, v in bands.items() if 200 <= f <= 1000 and v is not None]
    ref = sum(ref_vals) / len(ref_vals) if ref_vals else 0.0

    print(f"\nReponse en frequence (0 dB = moyenne 200-1000Hz = {ref:+.1f} dB brut)\n")
    print(f"{'Hz':>6}  {'dB':>6}  Niveau")
    for fc in BAND_CENTERS:
        v = bands[fc]
        if v is None:
            print(f"{fc:>6}  {'--':>6}  (pas de donnees)")
            continue
        rel = v - ref
        print(f"{fc:>6}  {rel:+6.1f}  {bar(rel)}")


if __name__ == "__main__":
    main()
