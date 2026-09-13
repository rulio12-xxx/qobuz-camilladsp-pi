#!/usr/bin/env python3
"""Pilotage automatique de la chaine audio (version fusionnee).
- Reveil ANTICIPE : des que l'app Qobuz se connecte au proxy
  ('Renderer set active: True'), on rallume le DAC + CamillaDSP sans
  attendre le son (un thread surveille les logs qobuz-proxy).
- Reveil sur SIGNAL : filet de securite pour Bluetooth/radio/SPDIF
  (detection de son dans les loopbacks).
- Extinction sur silence prolonge (IDLE_TIMEOUT), avec delai de grace
  apres un reveil pour ne pas couper si le son tarde a arriver.
Un seul cerveau : plus de conflit entre scripts separes.
"""

import os
import re
import struct
import subprocess
import threading
import time

from camilladsp import CamillaClient

# ------------- A ADAPTER -------------
USB_DEV = "3-2"
IDLE_TIMEOUT = 600          # secondes de pause avant extinction
DAC_WAKE_DELAY = 3
WAKE_GRACE = 60            # apres un reveil, on n'eteint pas avant ce delai (s)
# -------------------------------------

CDSP_HOST, CDSP_PORT = "127.0.0.1", 1234
POLL_ON = 5
WAKE_THRESHOLD = 1e-4
HWPARAMS = "/proc/asound/card10/pcm0p/sub0/hw_params"
QOBUZ_TRIGGER = "Renderer set active: True"

WAKE_DEVICES = [
    ("Qobuz",     "hw:10,1", "/proc/asound/card10/pcm0p/sub0/hw_params"),
    ("Bluetooth", "hw:11,1", "/proc/asound/card11/pcm0p/sub0/hw_params"),
    ("Fichiers",  "hw:10,1,1", "/proc/asound/card10/pcm0p/sub1/hw_params"),
    # ("Spdif",   "hw:3,0",  "/proc/asound/card3/pcm0c/sub0/hw_params"),
]

# drapeau partage : leve par le thread de surveillance des logs qobuz
_qobuz_connect = threading.Event()


def log(msg):
    print(msg, flush=True)


def usb_power5V(on: bool):
    subprocess.run(["uhubctl", "-l", "3", "-p", "2",
                    "-a", "on" if on else "off"], capture_output=True)
    log(f"USB hub3 port2 -> {'alimente' if on else 'coupe'}")


def _rate_of(hwparams_path: str) -> int:
    try:
        m = re.search(r"rate:\s*(\d+)", open(hwparams_path).read())
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return 44100


def wait_for_signal():
    """Ecoute en parallele les WAKE_DEVICES, True des qu'un signal apparait
    (ou False apres ~10 s). Interrompu immediatement si une connexion Qobuz
    est detectee entre-temps."""
    procs = []
    for name, dev, hwp in WAKE_DEVICES:
        rate = _rate_of(hwp)
        chunk = int(rate * 0.25) * 2 * 4
        try:
            p = subprocess.Popen(
                ["arecord", "-q", "-D", dev, "-f", "FLOAT_LE",
                 "-c", "2", "-r", str(rate), "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            procs.append((name, dev, chunk, p))
        except Exception as e:
            log(f"reveil: {name} ({dev}) indisponible ({e})")
    if not procs:
        time.sleep(1)
        return False
    try:
        for _ in range(40):
            if _qobuz_connect.is_set():
                return False  # laisse la boucle traiter le reveil Qobuz
            for name, dev, chunk, p in procs:
                if p.poll() is not None:
                    continue
                data = p.stdout.read(chunk)
                if not data:
                    continue
                n = len(data) // 4
                if n == 0:
                    continue
                samples = struct.unpack(f"<{n}f", data[: n * 4])
                if max(abs(x) for x in samples) > WAKE_THRESHOLD:
                    log(f"Signal detecte sur {name} ({dev})")
                    return True
        return False
    finally:
        for _, _, _, p in procs:
            try:
                p.kill()
            except Exception:
                pass


def qobuz_log_watcher():
    """Thread : suit les logs qobuz-proxy, leve le drapeau a chaque connexion."""
    while True:
        try:
            p = subprocess.Popen(
                ["journalctl", "-u", "qobuz-proxy", "-f", "-n", "0", "-o", "cat"],
                stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                if QOBUZ_TRIGGER in line:
                    log("Connexion Qobuz detectee (reveil anticipe)")
                    _qobuz_connect.set()
        except Exception as e:
            log(f"watcher qobuz: {e}")
            time.sleep(5)


def cdsp_state() -> str:
    try:
        client = CamillaClient(CDSP_HOST, CDSP_PORT)
        client.connect()
        state = str(client.general.state())
        client.disconnect()
        return state
    except Exception:
        return "unreachable"


def camilladsp_active() -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", "camilladsp"]).returncode == 0


def wait_dac(timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(f"/sys/bus/usb/devices/{USB_DEV}"):
            time.sleep(0.3)
            log("DAC detecte sur l'USB")
            return True
        time.sleep(0.2)
    log("DAC non detecte apres timeout")
    return False


def do_wake(raison):
    """Sequence commune de rallumage."""
    log(f"Reveil : {raison}")
    usb_power5V(True)
    wait_dac()
    subprocess.run(["amixer", "-c", "II", "sset", "DX5 II", "100%"],
                   capture_output=True)
    subprocess.run(["systemctl", "restart", "camilladsp"])
    _qobuz_connect.clear()
    return time.time()   # horodatage du reveil (pour le delai de grace)


def main():
    state = "on" if camilladsp_active() else "off"
    paused_since = None
    woke_at = 0.0
    last_s = None
    log(f"Etat initial detecte : {state}")

    threading.Thread(target=qobuz_log_watcher, daemon=True).start()

    while True:
        if state == "on":
            s = cdsp_state().upper()
            if s != last_s:
                log(f"Etat CamillaDSP : {s}")
                last_s = s
            if "PAUSED" in s or "INACTIVE" in s:
                # delai de grace : ne pas eteindre juste apres un reveil
                if woke_at and time.time() - woke_at < WAKE_GRACE:
                    pass
                elif paused_since is None:
                    paused_since = time.time()
                    log("CamillaDSP en pause, decompte lance")
                elif time.time() - paused_since > IDLE_TIMEOUT:
                    log("Inactivite prolongee : extinction")
                    subprocess.run(["systemctl", "stop", "camilladsp"])
                    time.sleep(2)
                    usb_power5V(False)
                    subprocess.run(["systemctl", "restart", "qobuz-proxy"])
                    log("qobuz-proxy redemarre (etat frais)")
                    state = "off"
                    paused_since = None
                    _qobuz_connect.clear()
            else:
                if paused_since is not None:
                    log(f"Etat {s} : decompte annule")
                paused_since = None
            time.sleep(POLL_ON)
        else:
            # relance externe de CamillaDSP -> on se resynchronise
            if camilladsp_active():
                woke_at = do_wake("CamillaDSP actif (relance externe)")
                state = "on"
                last_s = None
                continue
            # reveil anticipe : connexion Qobuz detectee par le thread
            if _qobuz_connect.is_set():
                woke_at = do_wake("connexion Qobuz")
                state = "on"
                last_s = None
                continue
            # filet de securite : signal audio detecte (BT, radio, spdif)
            if wait_for_signal():
                woke_at = do_wake("signal audio")
                state = "on"
                last_s = None


if __name__ == "__main__":
    main()
