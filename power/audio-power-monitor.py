#!/usr/bin/env python3
"""Pilotage automatique de la chaine audio :
- CamillaDSP en pause (silence) depuis IDLE_TIMEOUT -> stop CamillaDSP + deconnexion USB du DAC
- Signal detecte sur le loopback -> reconnexion USB, attente reveil DAC, redemarrage CamillaDSP
"""

import re
import struct
import subprocess
import time
import os

from camilladsp import CamillaClient

# ------------- A ADAPTER -------------
USB_DEV = "3-2"        # identifiant sysfs du DAC (voir instructions)
IDLE_TIMEOUT = 600       # secondes de pause avant extinction (600 = 10 min)
DAC_WAKE_DELAY = 3       # secondes laissees au DAC pour se reveiller
# -------------------------------------

CDSP_HOST, CDSP_PORT = "127.0.0.1", 1234
POLL_ON = 5              # periode de sonde quand la chaine est allumee
POLL_OFF = 2             # periode de sonde quand la chaine est eteinte
WAKE_THRESHOLD = 1e-4    # niveau minimal considere comme du signal
LOOPBACK_HW = "hw:10,1"  # face capture du loopback
HWPARAMS = "/proc/asound/card10/pcm0p/sub0/hw_params"


def log(msg):
    print(msg, flush=True)


def usb_power(on: bool):
    with open(f"/sys/bus/usb/devices/{USB_DEV}/authorized", "w") as f:
        f.write("1" if on else "0")
    log(f"USB {USB_DEV} -> {'connecte' if on else 'deconnecte'}")

def usb_power5V(on: bool):
    subprocess.run(["uhubctl", "-l", "3", "-p", "2",
                    "-a", "on" if on else "off"],
                   capture_output=True)
    log(f"USB hub3 port2 -> {'alimente' if on else 'coupe'}")

def loopback_rate() -> int:
    try:
        txt = open(HWPARAMS).read()
        m = re.search(r"rate:\s*(\d+)", txt)
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return 44100


def signal_present() -> bool:
    """Ecoute 1 s du loopback et cherche un niveau non nul."""
    rate = loopback_rate()
    try:
        p = subprocess.run(
            ["arecord", "-q", "-D", LOOPBACK_HW, "-f", "FLOAT_LE",
             "-c", "2", "-r", str(rate), "-d", "1", "-t", "raw"],
            capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        return False
    data = p.stdout
    n = len(data) // 4
    if n == 0:
        return False
    samples = struct.unpack(f"<{n}f", data[: n * 4])
    return max(abs(x) for x in samples) > WAKE_THRESHOLD

# ============================================================================
# REVEIL MULTI-SOURCES
# ============================================================================

WAKE_DEVICES = [
    ("Qobuz",     "hw:10,1", "/proc/asound/card10/pcm0p/sub0/hw_params"),
    ("Bluetooth", "hw:11,1", "/proc/asound/card11/pcm0p/sub0/hw_params"),
    # ("Spdif",   "hw:3,0",  "/proc/asound/card3/pcm0c/sub0/hw_params"),
]


def _rate_of(hwparams_path: str) -> int:
    try:
        m = re.search(r"rate:\s*(\d+)", open(hwparams_path).read())
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return 44100


def wait_for_signal():
    """Ecoute EN PARALLELE tous les WAKE_DEVICES, retourne True des qu'un
    signal apparait sur l'un d'eux (ou False apres ~10 s)."""
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
    """Attend que le DAC reapparaisse sur l'USB apres remise sous tension."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(f"/sys/bus/usb/devices/{USB_DEV}"):
            time.sleep(1.0)          # marge d'initialisation audio
            log("DAC detecte sur l'USB")
            return True
        time.sleep(0.2)
    log("DAC non detecte apres timeout")
    return False

def main():
    state = "on" if camilladsp_active() else "off"
    paused_since = None
    log(f"Etat initial detecte : {state}")
    #state = "on"
    #paused_since = None
    #log("Demarrage du moniteur audio-power")
    while True:
        if state == "on":
            s = cdsp_state().upper()
            if s != getattr(main, "last_s", None):
                log(f"Etat CamillaDSP : {s}")
                main.last_s = s
            if "PAUSED" in s or "INACTIVE" in s:
                if paused_since is None:
                    paused_since = time.time()
                    log("CamillaDSP en pause, decompte lance")
                elif time.time() - paused_since > IDLE_TIMEOUT:
                    log("Inactivite prolongee : extinction")
                    subprocess.run(["systemctl", "stop", "camilladsp"])
                    time.sleep(2)
                    #usb_power(False)
                    usb_power5V(False)
                    subprocess.run(["systemctl", "restart", "qobuz-proxy"])
                    log("qobuz-proxy redemarre (etat frais)")
                    state = "off"
                    paused_since = None
            else:
                if paused_since is not None:
                    log(f"Etat {s} : decompte annule")
                paused_since = None
            time.sleep(POLL_ON)
        else:
            if subprocess.run(["systemctl", "is-active", "--quiet", "camilladsp"]).returncode == 0:
                log("CamillaDSP actif (relance externe) : retour etat on")
                usb_power5V(True)
                #time.sleep(DAC_WAKE_DELAY)
                wait_dac()
                subprocess.run(["systemctl", "restart", "camilladsp"])
                state = "on"
                continue
            #if signal_present():
            if wait_for_signal():
                log("Signal detecte : rallumage")
                #usb_power(True)
                usb_power5V(True)
                #time.sleep(DAC_WAKE_DELAY)
                wait_dac()
                subprocess.run(["systemctl", "start", "camilladsp"])
                state = "on"
                time.sleep(2)
            #else:
            #    time.sleep(POLL_OFF)


if __name__ == "__main__":
    main()
