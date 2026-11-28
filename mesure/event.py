#!/usr/bin/env python3
"""Mesure de l'event bass-reflex en champ proche, directement sur le Pi (sans REW).

    python3 event.py gen                                  # cree ~/musique/event_G.wav et event_D.wav (une fois)
    python3 event.py mesure <session> <nom>               # joue + enregistre + deconvolue + sauvegarde
    python3 event.py analyse <session> [options cotes]    # analyse numerique de la session
    python3 event.py liste <session>                      # mesures deja faites
    python3 event.py selftest                             # test complet sur une enceinte simulee

<nom> : "woofer G", "woofer G2", "event G", "event G2", "event G b", "bruit G",
idem avec D. G = canal gauche (0), D = canal droit (1). Mettre le nom entre
guillemets. "bruit" enregistre sans jouer de son (bruit de fond, meme traitement).

Options d'analyse (voir event_analyse.py --help) :
    --d-membrane 330 --d-event 100 --l-event 250 --n-event 1 --vb 180 --vd-litres 8

Signal : un sweep log 10 Hz-20 kHz de 16 s, sur un seul canal, apres 7,5 s de
silence (reveil de la chaine), joue par MPD comme ir2.py, micro sur l'entree 1
du Scarlett. Le volume CamillaDSP est verifie avant chaque mesure (-40 dB max
par defaut, option --volume-max).

Phase : MPD ne demarre pas avec une latence fixe, donc deux mesures separees
n'ont pas de repere de temps commun. Woofer et event en champ proche etant a
phase minimale dans le grave, l'analyse reconstruit leur phase a partir du
module (meme methode que VituixCAD), ce qui rend inutile la boucle de
reference de REW. Valide par le selftest.
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

from sweep_dsp import generate_log_sweep, write_wav, read_wav_mono

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 44100
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0
MUSIQUE = "/home/rulio12/musique"
VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"
F1, F2 = 10.0, 20000.0
SWEEP_DUR = 16.0
WARMUP_S = 7.5
TAIL_S = 3.0
PRE_MS, WIN_MS, FADE_MS = 50, 1000, 150
VOLUME_MAX_DEFAUT = -40.0
OUT = os.path.join(HERE, "resultats", "event")
NOM_RE = re.compile(r"^(woofer|event|bruit)\s+([GD])(\s*\d*)(\s*[a-z]?)$", re.I)


def sweep():
    return generate_log_sweep(F1, F2, SWEEP_DUR, FS) * 0.7


def wav_path(cote):
    return os.path.join(MUSIQUE, f"event_{cote}.wav")


def gen():
    s = sweep()
    n = int((WARMUP_S + SWEEP_DUR + TAIL_S) * FS)
    for cote, ch in (("G", 0), ("D", 1)):
        st = np.zeros((n, 2))
        a = int(WARMUP_S * FS)
        st[a:a + len(s), ch] = s
        write_wav(wav_path(cote), st, FS, channels=2, sampwidth=3)
        print(f"OK : {wav_path(cote)}, {n / FS:.1f} s")
    subprocess.run(["mpc", "-q", "update", "--wait"])


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def snapshot():
    code = ("import json\nfrom camilladsp import CamillaClient\nc=CamillaClient('127.0.0.1',1234)\n"
            "c.connect()\nprint(json.dumps({'volume': c.volume.main_volume(), 'config': c.config.active()}))")
    out = subprocess.run([VENV_PY, "-c", code], capture_output=True, text=True).stdout
    return json.loads(out)


def record(path, cote, jouer=True):
    total = WARMUP_S + SWEEP_DUR + TAIL_S
    if jouer:
        mpc("clear"); mpc("add", os.path.basename(wav_path(cote)))
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS), "-c", "2",
                          "-d", str(int(total) + 3), path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    if jouer:
        mpc("play")
    p.wait()
    if jouer:
        mpc("stop")


def deconv(rec):
    s = sweep()
    n = len(rec) + len(s)
    nf = 1 << (n - 1).bit_length()
    X = np.fft.rfft(s, nf)
    Y = np.fft.rfft(rec, nf)
    f = np.fft.rfftfreq(nf, 1 / FS)
    inv = np.conj(X) / (np.abs(X) ** 2 + 1e-4 * np.max(np.abs(X) ** 2))
    inv[(f < F1 * 0.9) | (f > F2 * 1.02)] = 0
    return np.fft.irfft(Y * inv, nf)


def fenetre(ir, start):
    ln = int(WIN_MS / 1000 * FS)
    x = ir[start:start + ln].copy()
    nfade = int(FADE_MS / 1000 * FS)
    x[-nfade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, nfade)))
    return x


def extract(rec, bruit=False):
    """Reponse impulsionnelle fenetree (-50 ms / +950 ms autour du pic)."""
    ir = deconv(rec)
    a0 = int(WARMUP_S * FS)
    if bruit:
        start = a0 + int(0.3 * FS)
        return fenetre(ir, start), None
    zone = np.abs(ir[a0:a0 + int(1.5 * FS)])          # latence de la chaine < 1,5 s
    pk = a0 + int(np.argmax(zone))
    start = pk - int(PRE_MS / 1000 * FS)
    x = fenetre(ir, start)
    # bruit residuel : apres la reponse, avant la fin de l'enregistrement
    nz = ir[pk + int(1.2 * FS):pk + int(2.2 * FS)]
    return x, float(np.sqrt(np.mean(nz ** 2)) / np.max(np.abs(x)))


def fichier(session, nom):
    return os.path.join(OUT, session, nom.replace(" ", "_"))


def mesure(session, nom, volume_max):
    m = NOM_RE.match(nom.strip())
    if not m:
        sys.exit(f"Nom invalide : {nom!r}. Exemples : 'woofer G', 'event D2', 'bruit G'.")
    type_, cote = m.group(1).lower(), m.group(2).upper()
    if not os.path.exists(wav_path(cote)):
        sys.exit(f"{wav_path(cote)} absent : lancer d'abord  python3 event.py gen")
    snap = snapshot()
    if snap["volume"] > volume_max:
        sys.exit(f"Volume CamillaDSP {snap['volume']} dB > {volume_max} dB : baisser le volume "
                 f"(ou --volume-max si c'est voulu).")
    path = f"/tmp/event_{session}_{nom.replace(' ', '_')}.wav"
    record(path, cote, jouer=(type_ != "bruit"))
    rec, fs = read_wav_mono(path, channel=MIC_CHANNEL)
    if fs != FS:
        sys.exit(f"Enregistrement a {fs} Hz au lieu de {FS}")
    pic = 20 * np.log10(np.max(np.abs(rec)) + 1e-12)
    ir, bruit_rel = extract(rec, bruit=(type_ == "bruit"))
    os.makedirs(os.path.join(OUT, session), exist_ok=True)
    np.savez_compressed(fichier(session, nom) + ".npz", ir=ir, fs=FS)
    meta = {"nom": nom, "session": session, "date": datetime.datetime.now().isoformat(timespec="seconds"),
            "pic_micro_dbfs": round(float(pic), 1), "volume_db": snap["volume"],
            "bruit_rel_db": None if bruit_rel is None else round(20 * np.log10(bruit_rel), 1),
            "sweep": f"{F1:g}-{F2:g} Hz, {SWEEP_DUR:g} s, {FS} Hz"}
    json.dump({**meta, "config": snap["config"]}, open(fichier(session, nom) + ".json", "w"))
    print(f"{nom} : pic micro {pic:+.1f} dBFS, volume {snap['volume']} dB"
          + ("" if bruit_rel is None else f", bruit {meta['bruit_rel_db']} dB sous le pic"))
    if pic > -3:
        print("ATTENTION : micro proche de la saturation, baisser le gain du Scarlett et refaire tout le cote.")
    if type_ != "bruit" and pic < -40:
        print("ATTENTION : niveau tres faible, micro mal place ou gain du Scarlett trop bas.")


def charger_session(session):
    mes = {}
    for p in sorted(glob.glob(os.path.join(OUT, session, "*.npz"))):
        z = np.load(p)
        ir, fs = z["ir"], int(z["fs"])
        nf = 1 << 18
        H = np.fft.rfft(ir, nf)
        f = np.fft.rfftfreq(nf, 1 / fs)
        sel = (f >= 5) & (f <= 20000)
        nom = os.path.basename(p)[:-4].replace("_", " ")
        # pas de phase : pas de repere de temps commun entre deux mesures (voir en-tete)
        mes[nom] = dict(f=f[sel], spl=20 * np.log10(np.abs(H[sel]) + 1e-15), phase=None, notes="")
    return mes


def analyse(session, extra):
    import event_analyse
    mes = charger_session(session)
    if not mes:
        sys.exit(f"Aucune mesure dans {os.path.join(OUT, session)}")
    out = os.path.join(OUT, session, "analyse")
    return event_analyse.main(["--out", out] + extra, mes=mes)


def liste(session):
    for p in sorted(glob.glob(os.path.join(OUT, session, "*.json"))):
        m = json.load(open(p))
        print(f"{m['nom']:12} {m['date']}  pic {m['pic_micro_dbfs']:+.1f} dBFS  volume {m['volume_db']} dB")


# ---------------------------------------------------------------- auto-test
def _enceinte_simulee(fb, nf):
    """Reponses champ proche woofer et event d'un bass-reflex (alignement B4, Fb = fb),
    event avec resonances de tuyau a 520 et 1040 Hz. Retourne (ir_woofer, ir_event)."""
    f = np.fft.rfftfreq(nf, 1 / FS)
    s = 2j * np.pi * np.maximum(f, 1e-3)
    w0 = 2 * np.pi * fb
    D = s ** 4 + 2.613 * w0 * s ** 3 + 3.414 * w0 ** 2 * s ** 2 + 2.613 * w0 ** 3 * s + w0 ** 4
    Ud = s ** 2 * (s ** 2 + w0 * s / 15 + w0 ** 2) / D / (1 + s / (2 * np.pi * 800)) ** 2
    Up = -s ** 2 * w0 ** 2 / D / (1 + s / (2 * np.pi * 300))
    for fr, g in ((520, 8), (1040, 5)):
        wr = 2 * np.pi * fr
        Up = Up * (s ** 2 + s * wr * g / 12 + wr ** 2) / (s ** 2 + s * wr / 12 + wr ** 2)
    hw = Ud / 0.165
    hp = Up / 0.050                     # rapport des rayons event/membrane = 100/330
    return np.fft.irfft(hw, nf), np.fft.irfft(hp, nf)


def selftest():
    """Chaine complete simulee : sweep -> enceinte -> latence aleatoire -> bruit ->
    deconvolution -> fenetre -> analyse. Verifie Fb et les resonances de tuyau."""
    import event_analyse
    global OUT
    rng = np.random.default_rng(3)
    s = sweep()
    n = int((WARMUP_S + SWEEP_DUR + TAIL_S + 3) * FS)
    OUT = os.path.join("/tmp", "event_selftest")
    session = "simu"
    os.makedirs(os.path.join(OUT, session), exist_ok=True)
    ok = True
    for cote, fb in (("G", 36.0), ("D", 37.5)):
        irw, irp = _enceinte_simulee(fb, 1 << 16)
        for nom, h in ((f"woofer {cote}", irw), (f"event {cote}", irp), (f"bruit {cote}", None)):
            rec = np.zeros(n)
            if h is not None:
                lat = int(WARMUP_S * FS + rng.integers(int(0.05 * FS), int(0.6 * FS)))
                y = np.convolve(s, h[:int(0.8 * FS)])
                rec[lat:lat + len(y)] = y[:n - lat]
            rec = rec / 50 + 1e-5 * rng.standard_normal(n)
            ir, _ = extract(rec, bruit=h is None)
            np.savez_compressed(fichier(session, nom) + ".npz", ir=ir, fs=FS)
        res = analyse(session, ["--d-membrane", "330", "--d-event", "100"])["cotes"][cote]
        fb_m = res["fb_creux_woofer_hz"]
        tuyau = [p["f_hz"] for p in res["resonances_tuyau"]]
        e1 = abs(fb_m - fb) <= 0.5
        e2 = any(abs(t - 520) < 15 for t in tuyau) and any(abs(t - 1040) < 30 for t in tuyau)
        e3 = res.get("somme_f3_hz") is not None and abs(res["somme_f3_hz"] - fb) < 2.5
        print(f"selftest {cote} : Fb {fb_m} Hz (vrai {fb}) {'OK' if e1 else 'ECHEC'}, "
              f"tuyau {tuyau} {'OK' if e2 else 'ECHEC'}, "
              f"-3 dB somme {res.get('somme_f3_hz')} Hz (B4 : = Fb) {'OK' if e3 else 'ECHEC'}")
        ok &= e1 and e2 and e3
    print("SELFTEST", "OK" if ok else "ECHEC")
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "gen":
        gen()
    elif cmd == "mesure":
        args = sys.argv[2:]
        vmax = VOLUME_MAX_DEFAUT
        if "--volume-max" in args:
            i = args.index("--volume-max"); vmax = float(args[i + 1]); del args[i:i + 2]
        if len(args) < 2:
            sys.exit("Usage : python3 event.py mesure <session> \"woofer G\"")
        mesure(args[0], " ".join(args[1:]), vmax)
    elif cmd == "analyse":
        analyse(sys.argv[2], sys.argv[3:])
    elif cmd == "liste":
        liste(sys.argv[2])
    elif cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    else:
        sys.exit(__doc__)
