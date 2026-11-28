"""Reponse en frequence des filtres CamillaDSP (Peaking, shelf, passe-haut Butterworth, FIR)."""
import os, subprocess
import numpy as np, yaml
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FS = 44100
IGNORE = {"loud_bass", "loud_treble", "limiter"}

def git_yml(ref, path):
    return yaml.safe_load(subprocess.check_output(["git", "-C", R, "show", f"{ref}:{path}"]))

def biquad(b, a, f):
    z = np.exp(-1j * 2 * np.pi * f / FS)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)

def rbj(p, f):
    t, f0 = p["type"], p["freq"]; w = 2 * np.pi * f0 / FS; c, s = np.cos(w), np.sin(w)
    g = p.get("gain", 0); A = 10 ** (g / 40)
    if t == "Peaking":
        al = s / (2 * p["q"])
        return biquad([1 + al * A, -2 * c, 1 - al * A], [1 + al / A, -2 * c, 1 - al / A], f)
    if t in ("Lowshelf", "Highshelf"):
        if "q" in p: al = s / (2 * p["q"])
        else: al = s / 2 * np.sqrt((A + 1 / A) * (1 / (p["slope"] / 12) - 1) + 2)
        k = 2 * np.sqrt(A) * al
        if t == "Lowshelf":
            b = [A * ((A + 1) - (A - 1) * c + k), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - k)]
            a = [(A + 1) + (A - 1) * c + k, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - k]
        else:
            b = [A * ((A + 1) + (A - 1) * c + k), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - k)]
            a = [(A + 1) - (A - 1) * c + k, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - k]
        return biquad(b, a, f)
    raise ValueError(t)

def butter_hp(f0, order, f):
    h = np.ones(len(f), complex); w = 2 * np.pi * f0 / FS; c, s = np.cos(w), np.sin(w)
    for k in range(order // 2):
        q = 1 / (2 * np.cos(np.pi * (2 * k + 1) / (2 * order)))
        al = s / (2 * q)
        h *= biquad([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al], f)
    return h

def chain(cfg, ch, f):
    h = np.ones(len(f), complex)
    for st in cfg["pipeline"]:
        if st.get("type") != "Filter" or ch not in st.get("channels", []) or st.get("bypassed"):
            continue
        for n in st["names"]:
            if n in IGNORE: continue
            fl = cfg["filters"][n]; t, p = fl["type"], fl.get("parameters", {})
            if t == "Biquad" and p["type"] in ("Peaking", "Lowshelf", "Highshelf"):
                if p.get("gain"): h *= rbj(p, f)
            elif t == "BiquadCombo" and p["type"] == "ButterworthHighpass":
                h *= butter_hp(p["freq"], p["order"], f)
            elif t == "Conv":
                fir = np.fromfile(os.path.join(R, "mesure/fir", os.path.basename(p["filename"])), "<f4")
                h *= np.fft.rfft(fir, 2 * (len(f) - 1))[:len(f)] if len(fir) <= 2 * (len(f) - 1) else 1
            elif t in ("Gain", "Delay", "Limiter"):
                pass
            else:
                raise ValueError((n, t, p))
    return h

