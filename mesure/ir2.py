"""Reponses impulsionnelles G et D (meme horloge) et kick simule a l'oreille.

    python3 ir2.py gen                            # cree ~/musique/ir2_test.wav (une fois)
    python3 ir2.py mesure <etiquette>             # joue + enregistre + analyse + sauvegarde
    python3 ir2.py analyse <etiquette>            # re-analyse resultats/ir/<etiquette>.npz
    python3 ir2.py predit <etiquette> filtre.param=valeur ...   # effet calcule d'un reglage

Signal : deux sweeps log 20 Hz-20 kHz de 16 s, G puis D decale de 1 s (ils se
chevauchent). La deconvolution donne la reponse G a t0 et la reponse D a t0 + 1 s ;
avec 16 s de sweep, les distorsions harmoniques tombent avant t0 et ne melangent
pas les deux reponses. Ecart de 1 s seulement : la derive d'horloge DAC/Scarlett
(~30 ppm) n'y fait que ~30 us d'erreur.

Le kick a l'oreille = kick (fichier) convolue par la reponse mesuree : exact pour
une chaine lineaire, sans bruit, parfaitement repetable. G+D = somme des deux.
La prediction remplace dans le spectre des reponses la correction actuelle par
la correction proposee (filtres Peaking, gains, delais).
"""
import copy
import datetime
import json
import os
import subprocess
import sys
import time

import numpy as np

from sweep_dsp import generate_log_sweep, write_wav, read_wav_mono, band_average_db
import kick2

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 44100
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0
WAV = "/home/rulio12/musique/ir2_test.wav"
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"
SWEEP_DUR = 16.0
WARMUP_S = 7.5
OFFSET_D = 1.0
TAIL_S = 2.5
PRE_MS, POST_MS = 20, 700
CENTERS = [round(20 * 2 ** (i / 12), 2) for i in range(0, 120) if 20 * 2 ** (i / 12) <= 20000]
OUT = os.path.join(HERE, "resultats", "ir")


def sweep():
    return generate_log_sweep(20, 20000, SWEEP_DUR, FS) * 0.7


def gen():
    s = sweep()
    n = int((WARMUP_S + OFFSET_D + SWEEP_DUR + TAIL_S) * FS)
    st = np.zeros((n, 2))
    a = int(WARMUP_S * FS)
    st[a:a + len(s), 0] = s
    b = int((WARMUP_S + OFFSET_D) * FS)
    st[b:b + len(s), 1] = s
    write_wav(WAV, st, FS, channels=2, sampwidth=3)
    print(f"OK : {WAV}, {n / FS:.1f} s")


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def record(path):
    total = WARMUP_S + OFFSET_D + SWEEP_DUR + TAIL_S
    mpc("clear"); mpc("add", os.path.basename(WAV))
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS), "-c", "2",
                          "-d", str(int(total) + 3), path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    mpc("play")
    p.wait()
    mpc("stop")


def snapshot():
    code = ("import json\nfrom camilladsp import CamillaClient\nc=CamillaClient('127.0.0.1',1234)\n"
            "c.connect()\nprint(json.dumps({'volume': c.volume.main_volume(), 'config': c.config.active()}))")
    return json.loads(subprocess.run([VENV_PY, "-c", code], capture_output=True, text=True).stdout)


def extract(rec):
    """reponses G et D (fenetres -20/+700 ms) depuis l'enregistrement complet."""
    s = sweep()
    n = len(rec) + len(s)
    nf = 1 << (n - 1).bit_length()
    X = np.fft.rfft(s, nf)
    Y = np.fft.rfft(rec, nf)
    f = np.fft.rfftfreq(nf, 1 / FS)
    inv = np.conj(X) / (np.abs(X) ** 2 + 1e-3 * np.max(np.abs(X) ** 2))
    inv[(f < 18) | (f > 20500)] = 0
    ir = np.fft.irfft(Y * inv, nf)
    a0 = int(WARMUP_S * FS)
    zone = np.abs(ir[a0:a0 + int(0.8 * FS)])         # latence < 0,8 s
    pk = a0 + int(np.argmax(zone))
    # debut de fenetre commun : meme repere pour G et D (D exactement 1 s plus tard)
    start = pk - int(PRE_MS / 1000 * FS)
    ln = int((PRE_MS + POST_MS) / 1000 * FS)
    irL = ir[start:start + ln].copy()
    irR = ir[start + int(OFFSET_D * FS):start + int(OFFSET_D * FS) + ln].copy()
    # bruit : zone avant les distorsions harmoniques et apres les reponses
    noise = ir[start + int(1.9 * FS):start + int(1.9 * FS) + ln]
    return irL, irR, float(np.sqrt(np.mean(noise ** 2)) / np.max(np.abs(irL)))


# ---------- reponse complexe des filtres ----------

def peaking_h(f, fc, gain, q):
    A = 10 ** (gain / 40)
    w0 = 2 * np.pi * fc / FS
    al = np.sin(w0) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w0), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w0), 1 - al / A])
    z = np.exp(-1j * 2 * np.pi * f / FS)
    return (b[0] + b[1] * z + b[2] * z ** 2) / (a[0] + a[1] * z + a[2] * z ** 2)


def chain_h(cfg, ch, f):
    h = np.ones(len(f), complex)
    for step in cfg["pipeline"]:
        if step.get("type") != "Filter" or step.get("channels") != [ch] or step.get("bypassed"):
            continue
        for n in step["names"]:
            flt = cfg["filters"][n]
            p = flt["parameters"]
            if flt["type"] == "Biquad" and p.get("type") == "Peaking":
                if p["gain"]:
                    h *= peaking_h(f, p["freq"], p["gain"], p["q"])
            elif flt["type"] == "Gain":
                h *= 10 ** (p["gain"] / 20)
            elif flt["type"] == "Delay":
                d = p["delay"] / FS if p.get("unit") == "samples" else p["delay"] / 1000
                h *= np.exp(-1j * 2 * np.pi * f * d)
    return h


def apply_change(irs, cfg_old, cfg_new):
    out = {}
    for ch, idx in (("L", 0), ("R", 1)):
        x = irs[ch]
        nf = 1 << (len(x) + int(0.2 * FS) - 1).bit_length()
        f = np.fft.rfftfreq(nf, 1 / FS)
        H = np.fft.rfft(x, nf) * chain_h(cfg_new, idx, f) / chain_h(cfg_old, idx, f)
        out[ch] = np.fft.irfft(H, nf)[:len(x)]
    return out


# ---------- analyse ----------

def responses(irs):
    out = {}
    for name, x in (("L", irs["L"]), ("R", irs["R"]), ("GD", irs["L"] + irs["R"])):
        nf = 1 << (len(x) - 1).bit_length()
        X = np.fft.rfft(x, nf)
        f = np.fft.rfftfreq(nf, 1 / FS)
        b = band_average_db(f, 20 * np.log10(np.abs(X) + 1e-12), CENTERS, frac_octave=1 / 12)
        v = np.array([b[c] if b[c] is not None else np.nan for c in CENTERS])
        fc = np.array(CENTERS)
        out[name] = v - np.nanmean(v[(fc >= 200) & (fc <= 1000)])
    return out


def kick_metrics(irs):
    src = kick2.make_kick()
    n = int(0.6 * FS)
    src_pad = np.concatenate([src, np.zeros(n - len(src))])
    pre = int(PRE_MS / 1000 * FS)
    res = {}
    hf_s = kick2.band(src_pad, *kick2.CLIC_BAND)
    lf_s = kick2.band(src_pad, *kick2.CORPS_BAND)
    Es_clic = np.sum(hf_s[:int(0.006 * FS)] ** 2)
    Es_late = np.sum(hf_s[int(0.006 * FS):int(0.040 * FS)] ** 2)
    Es_corps = np.sum(lf_s[:int(0.3 * FS)] ** 2)
    el_s = kick2.envelope(lf_s, 8)
    on_s = int(np.argmax(el_s >= el_s.max() * 0.5))
    nl_s = kick2.db(el_s / el_s.max())
    sims = {}
    for name, ir in (("G", irs["L"]), ("D", irs["R"]), ("GD", irs["L"] + irs["R"])):
        y = np.convolve(src_pad, ir)[pre:pre + n]          # t=0 : arrivee du direct G
        sims[name] = y
        hf, lf = kick2.band(y, *kick2.CLIC_BAND), kick2.band(y, *kick2.CORPS_BAND)
        eh = kick2.envelope(hf, 0.3)
        ic = int(np.argmax(eh[:int(0.03 * FS)]))
        Ec = np.sum(hf[max(0, ic - int(0.001 * FS)):ic + int(0.006 * FS)] ** 2)
        El = np.sum(hf[ic + int(0.006 * FS):ic + int(0.040 * FS)] ** 2)
        Eb = np.sum(lf[:int(0.3 * FS)] ** 2)
        el = kick2.envelope(lf, 8)
        il = int(np.argmax(el))
        on = int(np.argmax(el >= el.max() * 0.5))
        nl = kick2.db(el / el.max())
        a, b = int(0.06 * FS), int(0.3 * FS)
        res[name] = {
            "clic_rel_db": round(float(10 * np.log10(Ec / Eb) - 10 * np.log10(Es_clic / Es_corps)), 2),
            "bavure_db": round(float(10 * np.log10(El / Ec)), 2),
            "corps_retard_ms": round(float((on - ic - on_s) / FS * 1000), 2),
            "traine_db": round(float(np.mean(nl[a:b] - nl_s[a:b])), 2),
            "t_clic_ms": round(float(ic / FS * 1000), 3),
            "enveloppes": {
                "t_ms": [round(i / FS * 1000, 2) for i in range(0, int(0.4 * FS), int(0.0005 * FS))],
                "clic": [round(float(v), 1) for v in kick2.db(eh / el.max())[:int(0.4 * FS):int(0.0005 * FS)]],
                "corps": [round(float(v), 1) for v in nl[:int(0.4 * FS):int(0.0005 * FS)]],
            },
        }
    res["source"] = {"bavure_db": round(float(10 * np.log10(Es_late / Es_clic)), 2),
                     "enveloppes": {"clic": [round(float(v), 1) for v in kick2.db(kick2.envelope(hf_s, 0.3) / el_s.max())[:int(0.4 * FS):int(0.0005 * FS)]],
                                    "corps": [round(float(v), 1) for v in nl_s[:int(0.4 * FS):int(0.0005 * FS)]]}}
    # ecart d'arrivee G - D : pic de l'aigu des deux reponses, sous l'echantillon
    def arrival(ir):
        h = kick2.envelope(kick2.band(ir, 1000, 16000), 0.05)
        k = int(np.argmax(h[:int(0.05 * FS)]))
        y0, y1, y2 = h[k - 1], h[k], h[k + 1]
        den = y0 - 2 * y1 + y2
        return k + (0.5 * (y0 - y2) / den if den else 0.0)
    res["ecart_GD_ms"] = round(float((arrival(irs["L"]) - arrival(irs["R"])) / FS * 1000), 3)
    return res, sims


def show(m, title=""):
    if title:
        print(title)
    print(f"  ecart d'arrivee G - D : {m['ecart_GD_ms']:+.3f} ms")
    print(f"  {'':20}{'G':>9}{'D':>9}{'G+D':>9}")
    for k, name in (("clic_rel_db", "Clic relatif (dB)"), ("bavure_db", "Bavure (dB)"),
                    ("corps_retard_ms", "Retard corps (ms)"), ("traine_db", "Traine corps (dB)")):
        print(f"  {name:20}" + "".join(f"{m[t][k]:>+9.2f}" for t in ("G", "D", "GD")))
    print(f"  (source : clic 0, bavure {m['source']['bavure_db']:+.1f}, retard 0, traine 0)")


def save(label, irs, snap, noise):
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(os.path.join(OUT, f"{label}.npz"), L=irs["L"], R=irs["R"])
    json.dump({"etiquette": label, "date": datetime.date.today().isoformat(), "bruit_rel": noise, **snap},
              open(os.path.join(OUT, f"{label}.json"), "w"))


def load(label):
    z = np.load(os.path.join(OUT, f"{label}.npz"))
    meta = json.load(open(os.path.join(OUT, f"{label}.json")))
    return {"L": z["L"], "R": z["R"]}, meta


def summary(irs, label):
    m, _ = kick_metrics(irs)
    r = responses(irs)
    show(m, f"== {label}")
    fc = np.array(CENTERS)
    sel = (fc >= 45) & (fc <= 200)
    lr = np.abs(r["L"][sel] - r["R"][sel])
    print(f"  grave 45-200 Hz : ecart G-D moyen {np.nanmean(lr):.1f} dB (max {np.nanmax(lr):.1f})")
    return m, r


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gen":
        gen()
    elif cmd == "mesure":
        label = sys.argv[2]
        snap = snapshot()
        path = f"/tmp/ir2_{label}.wav"
        record(path)
        rec, _ = read_wav_mono(path, channel=MIC_CHANNEL)
        peak = 20 * np.log10(np.max(np.abs(rec)))
        irL, irR, noise = extract(rec)
        irs = {"L": irL, "R": irR}
        save(label, irs, snap, noise)
        print(f"pic micro {peak:+.1f} dBFS, bruit de la reponse {20 * np.log10(noise):.0f} dB sous le pic, "
              f"volume {snap['volume']} dB")
        summary(irs, label)
    elif cmd == "analyse":
        irs, meta = load(sys.argv[2])
        summary(irs, sys.argv[2])
    elif cmd == "predit":
        label = sys.argv[2]
        irs, meta = load(label)
        new = copy.deepcopy(meta["config"])
        for c in sys.argv[3:]:
            k, v = c.split("=")
            fl, p = k.split(".")
            val = {"true": True, "false": False}.get(v.lower())
            if val is None:
                try:
                    val = float(v)
                except ValueError:
                    val = v
            new["filters"][fl]["parameters"][p] = val
        summary(irs, label + " (mesure)")
        summary(apply_change(irs, meta["config"], new), "prediction : " + " ".join(sys.argv[3:]))
