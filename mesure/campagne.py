"""Campagne de mesure multi-niveaux : reponse L/R + test kick a plusieurs volumes.

Usage :
    python3 campagne.py <etiquette> [vol1 vol2 ...]
    ex : python3 campagne.py base -36 -28 -21 -14

Pour chaque volume CamillaDSP : sweep voie L, sweep voie R, test kick (L+R).
Le loudness est coupe pendant la campagne (pour mesurer l'EQ seule : son effet
est connu par calcul, cf loudness.py) puis restaure, ainsi que le volume.

Resultats : resultats/<date>_<etiquette>/
  - config_active.json : copie exacte de la config CamillaDSP live mesuree
  - niveaux.json       : toutes les mesures (dB absolus, non normalises)
  - kick_<vol>.json    : enveloppes du kick par niveau
Comparaison : compare.py <dossier_A> <dossier_B>
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve, band_average_db

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 44100
SWEEP_DUR = 8.0
WARMUP_S = 7.5
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0
LOUD_FLAG = "/home/rulio12/loudness/enabled"
MIC_PEAK_LIMIT = -1.0   # dBFS : au-dessus, on arrete de monter le volume

BANDS_3 = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
           630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000,
           10000, 12500, 16000]
BANDS_LF = list(range(20, 201, 2))   # 1/12 octave, pour les resonances
CENTERS_12 = [round(20 * 2 ** (i / 12), 2) for i in range(0, 120) if 20 * 2 ** (i / 12) <= 20000]  # = courbes.py


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"   # seul python avec le module camilladsp


def cdsp(code):
    """Execute du code CamillaClient (variable c connectee) dans le venv, renvoie stdout."""
    full = ("import json\nfrom camilladsp import CamillaClient\n"
            "c=CamillaClient('127.0.0.1',1234)\nc.connect()\n" + code)
    r = subprocess.run([VENV_PY, "-c", full], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r.stdout


def set_vol(db):
    cdsp(f"c.volume.set_main_volume({db})")


def loud_zero():
    cdsp("c.config.set_value('/filters/loud_bass/parameters/gain', 0.0)\n"
         "c.config.set_value('/filters/loud_treble/parameters/gain', 0.0)")


def sweep(channel_name, vol):
    fname = f"warm_sweep_{channel_name}.wav"
    rec = f"/tmp/camp_{channel_name}_{vol}.wav"
    mpc("clear"); mpc("add", fname); mpc("play")
    time.sleep(WARMUP_S)
    subprocess.run(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS), "-c", "2",
                    "-d", str(int(SWEEP_DUR) + 3), rec],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mpc("stop")
    s = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    r, _ = read_wav_mono(rec, channel=MIC_CHANNEL)
    peak = 20 * np.log10(max(np.abs(r).max(), 1e-9))
    f, m = deconvolve(s, r, FS)
    b3 = band_average_db(f, m, BANDS_3)
    blf = band_average_db(f, m, BANDS_LF, frac_octave=1 / 12)
    b12 = band_average_db(f, m, CENTERS_12, frac_octave=1 / 12)
    return {"peak_dbfs": round(float(peak), 2),
            "bands_12": [round(float(b12[k]), 2) if b12[k] is not None else None for k in CENTERS_12],
            "bands_3": {str(k): (round(float(v), 2) if v is not None else None) for k, v in b3.items()},
            "bands_lf": {str(k): (round(float(v), 2) if v is not None else None) for k, v in blf.items()}}


def kick(vol, outdir):
    subprocess.run([sys.executable, "play_record_kick.py"], cwd=HERE,
                   stdout=subprocess.DEVNULL)
    out = subprocess.run([sys.executable, "measure_kick.py"], cwd=HERE,
                         capture_output=True, text=True).stdout
    with open("/tmp/kick_compare.json") as f:
        k = json.load(f)
    shutil.copy("/tmp/kick_compare.json", os.path.join(outdir, f"kick_{vol}.json"))
    return {"decay_ms": k["decay_rec_ms"], "src_decay_ms": k["decay_src_ms"],
            "peak_dbfs": round(k["peak_dbfs"], 2), "log": out.strip().splitlines()}


def main():
    label = sys.argv[1]
    vols = [float(v) for v in sys.argv[2:]] or [-36.0, -28.0, -21.0, -14.0]
    day = datetime.date.today().isoformat()
    outdir = os.path.join(HERE, "resultats", f"{day}_{label}")
    os.makedirs(outdir, exist_ok=True)

    vol0 = float(cdsp("print(c.volume.main_volume())"))
    loud0 = os.path.exists(LOUD_FLAG)
    snap = cdsp("print(json.dumps({'fichier': c.config.file_path(), 'config': c.config.active()}, indent=1))")
    with open(os.path.join(outdir, "config_active.json"), "w") as f:
        f.write(snap)

    results = {"etiquette": label, "date": day, "volume_initial": vol0,
               "loudness_initial": loud0, "loudness_pendant": False, "niveaux": {}}
    try:
        if loud0:
            os.remove(LOUD_FLAG)
        loud_zero()
        print("Amorcage...", flush=True)
        mpc("clear"); mpc("add", "warm_sweep_L.wav"); mpc("play")
        time.sleep(WARMUP_S + SWEEP_DUR + 1.0)
        mpc("stop"); time.sleep(0.5)

        for vol in vols:
            set_vol(vol)
            loud_zero()
            time.sleep(2.5)   # laisse passer le cycle du service loudness (periode 2 s)
            key = f"{vol:g}"
            print(f"== volume {key} dB", flush=True)
            L = sweep("L", key); print(f"  L pic micro {L['peak_dbfs']:+.1f} dBFS", flush=True)
            R = sweep("R", key); print(f"  R pic micro {R['peak_dbfs']:+.1f} dBFS", flush=True)
            K = kick(key, outdir)
            print(f"  kick : chute -20dB {K['decay_ms']} ms, pic {K['peak_dbfs']:+.1f} dBFS", flush=True)
            results["niveaux"][key] = {"L": L, "R": R, "kick": K}
            with open(os.path.join(outdir, "niveaux.json"), "w") as f:
                json.dump(results, f, indent=1)
            if max(L["peak_dbfs"], R["peak_dbfs"], K["peak_dbfs"]) > MIC_PEAK_LIMIT:
                print("  micro proche de la saturation : arret de la montee", flush=True)
                break
    finally:
        mpc("stop")
        set_vol(vol0)
        if loud0:
            open(LOUD_FLAG, "w").close()
        print(f"Restaure : volume {vol0} dB, loudness {'on' if loud0 else 'off'}")
        print("Resultats ->", outdir)


if __name__ == "__main__":
    main()
