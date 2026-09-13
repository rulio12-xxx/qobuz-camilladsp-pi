#!/usr/bin/env python3
"""Loudness automatique : compense grave et aigu selon le niveau global.

Niveau global = volume USB du DAC + volume principal CamillaDSP.
(la molette physique du DAC n'est pas visible et reste hors calcul)

A la reference (REF_DB) : compensation nulle.
En dessous : grave +1 dB par BASS_STEP dB manquants, aigu a la moitie,
plafonnes a BASS_MAX / TREBLE_MAX.

Les gains sont appliques par set_value sur les filtres loud_bass /
loud_treble : pas de rechargement, donc pas de coupure.
"""

import os
import re
import subprocess
import time

from camilladsp import CamillaClient

REF_DB = -17.5          # niveau global de reference (compensation nulle)
BASS_STEP = 4.0         # dB de baisse pour +1 dB de grave
BASS_MAX = 8.0          # compensation grave maximale
TREBLE_RATIO = 0.5      # l'aigu suit le grave, a moitie
PERIOD = 2.0            # periode de mise a jour (s)
MIN_DELTA = 0.3         # on n'ecrit que si le gain change d'au moins ca

ENABLE_FILE = "/home/rulio12/loudness/enabled"
DAC_CTL = "DX5 II"
HOST, PORT = "127.0.0.1", 1234


def log(m):
    print(m, flush=True)


def enabled():
    return os.path.exists(ENABLE_FILE)


def dac_db():
    try:
        out = subprocess.run(["amixer", "-c", "II", "sget", DAC_CTL],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"\[(-?\d+\.\d+)dB\]", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def gains_for(level):
    """Retourne (grave, aigu) en dB pour un niveau global donne."""
    manque = max(0.0, REF_DB - level)
    bass = min(BASS_MAX, manque / BASS_STEP)
    return round(bass, 1), round(bass * TREBLE_RATIO, 1)


def main():
    client = None
    applied = (None, None)
    last_state = None

    while True:
        try:
            if client is None:
                client = CamillaClient(HOST, PORT)
                client.connect()
                applied = (None, None)

            on = enabled()
            if on != last_state:
                log(f"Loudness : {'actif' if on else 'inactif'}")
                last_state = on

            if not on:
                if applied != (0.0, 0.0):
                    client.config.set_value("/filters/loud_bass/parameters/gain", 0.0)
                    client.config.set_value("/filters/loud_treble/parameters/gain", 0.0)
                    applied = (0.0, 0.0)
                    log("gains remis a zero")
                time.sleep(PERIOD)
                continue

            dac = dac_db()
            cdsp = client.volume.main_volume()
            if dac is None or cdsp is None:
                time.sleep(PERIOD)
                continue

            bass, treble = gains_for(dac + cdsp)
            if (applied[0] is None
                    or abs(bass - applied[0]) >= MIN_DELTA
                    or abs(treble - applied[1]) >= MIN_DELTA):
                client.config.set_value("/filters/loud_bass/parameters/gain", bass)
                client.config.set_value("/filters/loud_treble/parameters/gain", treble)
                applied = (bass, treble)
                log(f"niveau {dac + cdsp:+.1f} dB -> grave {bass:+.1f} / aigu {treble:+.1f}")

        except Exception as e:
            log(f"erreur ({e}) - reconnexion")
            client = None
            time.sleep(5)
            continue

        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
