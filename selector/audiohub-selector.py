#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audiohub-selector : demon de selection de source pour AudioHub DSP V1

Priorite STRICTE :
    Qobuz > Optique > Coax1 > Coax2 (phono) > Bluetooth

ARCHITECTURE (v2 : un loopback par source)
    qobuz-proxy      -> hw:10,0   (carte 10)   CamillaDSP capture hw:10,1
    bluealsa-aplay   -> hw:11,0   (carte 11)   CamillaDSP capture hw:11,1
    WM8805 (a venir) -> carte I2S               CamillaDSP capture hw:X,0

Chaque source possede son propre tuyau : plus aucune exclusivite, plus besoin
d'arreter qobuz-proxy. La bascule se fait cote CamillaDSP, qui recharge la
config pointant sur la bonne capture (via son websocket, port 1234).
"""

import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BT_MAC = "5C:33:7B:D5:3B:3B"                 # Pixel 7a
BT_LOOPBACK = "plughw:11,0,0"                # loopback dedie au Bluetooth

CFG_DIR = "/home/rulio12/camilladsp/configs"
CONFIG = {
    "Qobuz":     f"{CFG_DIR}/camilladsp-qobuz.yml",
    "Bluetooth": f"{CFG_DIR}/camilladsp-bluetooth.yml",
}

CAMILLA_HOST, CAMILLA_PORT = "127.0.0.1", 1234

# Detection Qobuz : cote 'playback' du loopback 10
QOBUZ_STATUS = "/proc/asound/Loopback/pcm0p/sub0/status"

T_ACTIVE, T_SILENCE = 2.0, 5.0
T_QUARANTINE, POLL = 30.0, 0.5

LOCK_FILE = "/run/audiohub/manual.lock"
ENABLE_SPDIF = False


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# PILOTAGE DE CAMILLADSP
# ---------------------------------------------------------------------------

class Camilla:
    """Recharge la config de CamillaDSP. Tolerant aux versions de pycamilladsp."""

    def __init__(self):
        self.cdsp = None

    def _connect(self):
        if self.cdsp is not None:
            return True
        try:
            try:
                from camilladsp import CamillaClient as Client
            except ImportError:
                from camilladsp import CamillaConnection as Client
            self.cdsp = Client(CAMILLA_HOST, CAMILLA_PORT)
            self.cdsp.connect()
            return True
        except Exception as e:
            log(f"CamillaDSP : connexion impossible ({e})")
            self.cdsp = None
            return False

    def load(self, path):
        if not os.path.exists(path):
            log(f"CamillaDSP : config introuvable : {path}")
            return
        if not self._connect():
            return
        try:
            try:                                    # pycamilladsp >= 2
                self.cdsp.config.set_file_path(path)
                self.cdsp.general.reload()
            except AttributeError:                  # pycamilladsp 1.x
                self.cdsp.set_config_name(path)
                self.cdsp.reload()
            log(f"CamillaDSP : config chargee -> {os.path.basename(path)}")
        except Exception as e:
            log(f"CamillaDSP : echec du rechargement ({e})")
            self.cdsp = None                        # forcer une reconnexion


camilla = Camilla()


# ---------------------------------------------------------------------------
# SOURCES
# ---------------------------------------------------------------------------

@dataclass
class Source:
    name: str
    priority: int
    always_on: bool = False

    _debounced: bool = field(default=False, init=False)
    _since: float = field(default=0.0, init=False)
    _last_raw: bool = field(default=False, init=False)
    _quarantine_until: float = field(default=0.0, init=False)

    def raw_active(self) -> bool:
        raise NotImplementedError

    def start(self):
        camilla.load(CONFIG[self.name])

    def stop(self):
        pass

    def update(self, now):
        try:
            raw = self.raw_active()
        except Exception as e:
            log(f"{self.name}: erreur de detection ({e})")
            raw = False

        if raw != self._last_raw:
            self._last_raw = raw
            self._since = now
            return

        held = now - self._since
        if raw and not self._debounced and held >= T_ACTIVE:
            self._debounced = True
            log(f"{self.name}: active")
        elif not raw and self._debounced and held >= T_SILENCE:
            self._debounced = False
            log(f"{self.name}: silencieuse")

    def available(self, now):
        return self._debounced and now >= self._quarantine_until

    def quarantine(self, now):
        self._quarantine_until = now + T_QUARANTINE
        self._debounced = False
        self._since = now
        log(f"{self.name}: quarantaine {T_QUARANTINE:.0f} s")


class QobuzSource(Source):
    """Le proxy garde le device ouvert en permanence : seul 'RUNNING' compte."""

    def raw_active(self):
        try:
            txt = open(QOBUZ_STATUS).read()
        except FileNotFoundError:
            return False
        return "state: RUNNING" in txt


class BluetoothSource(Source):
    """Actif des qu'un appareil A2DP quelconque emet (Running: true)."""

    def _sources(self):
        try:
            out = subprocess.run(["bluealsactl", "list-pcms"],
                                 capture_output=True, text=True, timeout=3).stdout
        except Exception:
            return []
        return [l.strip() for l in out.splitlines()
                if l.strip().endswith("source")]

    def raw_active(self):
        for path in self._sources():
            try:
                out = subprocess.run(["bluealsactl", "info", path],
                                     capture_output=True, text=True,
                                     timeout=3).stdout
            except Exception:
                return True
            if "running: true" in out.lower():
                return True
        return False


class Aplay:
    """bluealsa-aplay SANS MAC : joue tout appareil connecte, chacun son tour."""

    def __init__(self):
        self.proc = None

    def ensure(self):
        if self.proc and self.proc.poll() is None:
            return
        cmd = ["bluealsa-aplay", f"--pcm={BT_LOOPBACK}"]
        log("Lancement : " + " ".join(cmd))
        self.proc = subprocess.Popen(cmd,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------------------
# BOUCLE PRINCIPALE
# ---------------------------------------------------------------------------

def manual_lock():
    try:
        return open(LOCK_FILE).read().strip() or None
    except OSError:
        return None


def main():
    qobuz = QobuzSource("Qobuz", priority=0)
    bt = BluetoothSource("Bluetooth", priority=4)

    sources = [qobuz]
    if ENABLE_SPDIF:
        sources += [
            SpdifSource("Optique", priority=1, rxsel=0),
            SpdifSource("Coax1",   priority=2, rxsel=1),
            SpdifSource("Coax2",   priority=3, rxsel=2, always_on=True),
        ]
    sources.append(bt)
    sources.sort(key=lambda s: s.priority)

    aplay = Aplay()
    current = None
    running = True

    def on_signal(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    log("Demarrage - priorite stricte : " + " > ".join(s.name for s in sources))

    while running:
        now = time.monotonic()
        aplay.ensure()

        for s in sources:
            s.update(now)

        forced = manual_lock()
        if forced:
            wanted = next((s for s in sources
                           if s.name.lower() == forced.lower()), current)
        else:
            wanted = next((s for s in sources if s.available(now)), current)

        if wanted is not current:
            if current:
                current.stop()
            if wanted:
                wanted.start()
            log(f"--> source active : {wanted.name if wanted else 'aucune'}")
            current = wanted
            # TODO : ecran ST7789 + LED

        time.sleep(POLL)

    log("Arret")
    aplay.stop()


if __name__ == "__main__":
    main()
