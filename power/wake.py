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
