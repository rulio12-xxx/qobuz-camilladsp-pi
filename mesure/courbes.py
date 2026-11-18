"""Courbes 1/12 octave (20 Hz-20 kHz) d'une ou plusieurs campagnes, pour l'affichage.

    python3 courbes.py <sortie.json> resultats/<campagne1> [resultats/<campagne2> ...]

Pour chaque campagne et chaque niveau :
  - "mesure"   : reponse mesuree au micro (avec la correction de cette campagne)
  - "brut"     : reponse sans correction = mesure - reponse calculee des filtres
                 CamillaDSP de la voie (config_active.json, loudness force a 0,
                 preamp exclu car constant)
  - "eq"       : reponse calculee de la correction seule
Toutes les courbes sont recalees sur leur moyenne 200-1000 Hz (0 dB).

Les courbes fines viennent de niveaux.json ("bands_12") ; si absentes, elles sont
recalculees depuis les enregistrements /tmp/camp_<voie>_<vol>.wav s'ils existent.
"""
import json
import os
import sys

import numpy as np

from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve, band_average_db

FS = 44100
SWEEP_DUR = 8.0
MIC_CHANNEL = 0
CENTERS = [round(20 * 2 ** (i / 12), 2) for i in range(0, 120) if 20 * 2 ** (i / 12) <= 20000]
SKIP = {"preamp", "loud_bass", "loud_treble", "limiter", "delay_L", "delay_R"}


def peaking_db(f, fc, gain, q, fs=FS):
    A = 10 ** (gain / 40)
    w0 = 2 * np.pi * fc / fs
    al = np.sin(w0) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w0), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w0), 1 - al / A])
    z = np.exp(-1j * 2 * np.pi * np.asarray(f) / fs)
    h = (b[0] + b[1] * z + b[2] * z ** 2) / (a[0] + a[1] * z + a[2] * z ** 2)
    return 20 * np.log10(np.abs(h))


def eq_response(cfg, ch, f):
    names = []
    for step in cfg["pipeline"]:
        if step.get("type") == "Filter" and step.get("channels") == [ch] and not step.get("bypassed"):
            names += step["names"]
    tot = np.zeros(len(f))
    for n in names:
        if n in SKIP:
            continue
        flt = cfg["filters"][n]
        p = flt["parameters"]
        if flt["type"] == "Biquad" and p["type"] == "Peaking":
            if p["gain"]:
                tot += peaking_db(f, p["freq"], p["gain"], p["q"])
        elif flt["type"] == "Gain":
            tot += p["gain"]
        else:
            raise ValueError(f"filtre non gere : {n} {flt['type']} {p.get('type')}")
    return tot


def norm(vals, f):
    f = np.asarray(f)
    m = (f >= 200) & (f <= 1000)
    return vals - np.nanmean(vals[m])


def fine_from_wav(path):
    s = generate_log_sweep(20, 20000, SWEEP_DUR, FS)
    r, _ = read_wav_mono(path, channel=MIC_CHANNEL)
    fr, m = deconvolve(s, r, FS)
    b = band_average_db(fr, m, CENTERS, frac_octave=1 / 12)
    return [b[c] for c in CENTERS]


def main():
    out_path, dirs = sys.argv[1], sys.argv[2:]
    out = {"freqs": CENTERS, "campagnes": []}
    f = np.array(CENTERS)
    for d in dirs:
        res = json.load(open(os.path.join(d, "niveaux.json")))
        cfg = json.load(open(os.path.join(d, "config_active.json")))["config"]
        camp = {"etiquette": res["etiquette"], "date": res["date"], "niveaux": {}}
        eq = {"L": eq_response(cfg, 0, f), "R": eq_response(cfg, 1, f)}
        for vol, lv in res["niveaux"].items():
            entry = {}
            for ch in ("L", "R"):
                fine = lv[ch].get("bands_12")
                if fine is None:
                    wav = f"/tmp/camp_{ch}_{vol}.wav"
                    if not os.path.exists(wav):
                        continue
                    fine = fine_from_wav(wav)
                    lv[ch]["bands_12"] = [round(float(v), 2) if v is not None else None for v in fine]
                meas = np.array([np.nan if v is None else v for v in fine], dtype=float)
                clean = lambda a: [None if np.isnan(v) else round(float(v), 2) for v in a]
                entry[ch] = {
                    "mesure": clean(norm(meas, f)),
                    "brut": clean(norm(meas - eq[ch], f)),
                    "eq": np.round(eq[ch] - np.mean(eq[ch][(f >= 200) & (f <= 1000)]), 2).tolist(),
                    "pic_micro": lv[ch]["peak_dbfs"],
                }
            entry["kick_ms"] = lv["kick"]["decay_ms"]
            camp["niveaux"][vol] = entry
        # memorise les courbes fines recalculees
        json.dump(res, open(os.path.join(d, "niveaux.json"), "w"), indent=1)
        out["campagnes"].append(camp)
    json.dump(out, open(out_path, "w"))
    print("OK ->", out_path)


if __name__ == "__main__":
    main()
