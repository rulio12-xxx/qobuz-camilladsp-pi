"""Test kick v2 : clic et corps, par voie, en une seule lecture.

    python3 kick2.py gen                    # cree ~/musique/kick2_test.wav (une fois)
    python3 kick2.py mesure <etiquette>     # joue + enregistre + analyse + sauvegarde
    python3 kick2.py analyse <wav> [etiq]   # re-analyse un enregistrement existant

Fichier de test : 7,5 s de silence (le temps que la lecture demarre), puis
3 tours de [coup G seul, coup D seul, coup G+D], un coup par seconde.
La lecture est faite deux fois : une a blanc (reveil de la chaine), une
enregistree. Comme les 9 coups sont dans la meme lecture, l'ecart d'arrivee
G/D a la position d'ecoute est mesure exactement (meme horloge).

Mesures, moyennees sur les 3 tours, pour G, D et G+D :
  clic_rel_db    niveau du clic (1,5-8 kHz) relatif au corps (40-120 Hz),
                 compare a la source. 0 = meme dosage que le fichier.
  clic_ms        largeur du clic a -10 dB. Plus petit = plus net.
  bavure_db      energie du clic entre 3 et 30 ms apres son pic, relative au
                 pic (reflexions, resonances de l'aigu). Plus bas = plus net.
  corps_retard_ms  retard du pic du corps par rapport au clic, moins le meme
                 ecart dans la source. 0 = corps et clic arrivent ensemble.
  traine_db      exces moyen de l'enveloppe du corps sur la source entre 60
                 et 300 ms (dB). 0 = pas de traine ajoutee par la piece.
  corps_20db_ms  temps de chute de -20 dB de l'enveloppe lissee du corps.
Et ecart_GD_ms : arrivee du clic G moins arrivee du clic D (positif = G en retard).
"""
import datetime
import json
import os
import subprocess
import sys
import time

import numpy as np

from sweep_dsp import write_wav, read_wav_mono

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 44100
DEVICE = "hw:USB,0"
MIC_CHANNEL = 0
WAV = "/home/rulio12/musique/kick2_test.wav"
WARMUP_S = 7.5
PERIOD_S = 1.0
TOURS = 6
ORDRE = ["G", "D", "GD"]
TAIL_S = 1.5

# meme kick que gen_kick.py (v1), pour rester comparable
F_START, F_END, TAU_PITCH, TAU_AMP, KICK_DUR = 150.0, 55.0, 0.045, 0.22, 0.5
CLICK_DUR, CLICK_LEVEL = 0.004, 0.35

CLIC_BAND = (1500, 8000)
CORPS_BAND = (40, 120)


def make_kick():
    n = int(KICK_DUR * FS)
    t = np.arange(n) / FS
    pitch = F_END + (F_START - F_END) * np.exp(-t / TAU_PITCH)
    body = np.sin(2 * np.pi * np.cumsum(pitch) / FS) * np.exp(-t / TAU_AMP)
    rng = np.random.default_rng(42)
    cn = int(CLICK_DUR * FS)
    click = np.zeros(n)
    click[:cn] = rng.uniform(-1, 1, cn) * np.exp(-np.arange(cn) / (CLICK_DUR * FS / 4)) * CLICK_LEVEL
    k = body + click
    k = k / np.max(np.abs(k)) * 0.9
    fn = int(0.002 * FS)
    k[-fn:] *= np.linspace(1, 0, fn)
    return k


def schedule():
    """[(type, tour, debut_s)] dans le fichier."""
    out, t = [], WARMUP_S
    for tour in range(TOURS):
        for typ in ORDRE:
            out.append((typ, tour, t))
            t += PERIOD_S
    return out, t + TAIL_S


def gen():
    k = make_kick()
    sch, total = schedule()
    st = np.zeros((int(total * FS), 2))
    for typ, _, t0 in sch:
        i = int(t0 * FS)
        if "G" in typ:
            st[i:i + len(k), 0] += k
        if "D" in typ:
            st[i:i + len(k), 1] += k
    write_wav(WAV, st, FS, channels=2, sampwidth=3)
    print(f"OK : {WAV}, {total:.1f} s, {len(sch)} coups")


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


def play_record(rec):
    _, total = schedule()
    mpc("clear"); mpc("add", os.path.basename(WAV)); mpc("play")
    time.sleep(total + 1.0)
    mpc("stop"); time.sleep(0.5)
    mpc("clear"); mpc("add", os.path.basename(WAV))
    p = subprocess.Popen(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS), "-c", "2",
                          "-d", str(int(total) + 3), rec],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    mpc("play")
    p.wait()
    mpc("stop")


# ---------- traitement du signal ----------

def band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FS)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def envelope(x, smooth_ms):
    """Enveloppe d'amplitude (signal analytique) lissee."""
    n = len(x)
    X = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1
    if n % 2 == 0:
        h[n // 2] = 1
        h[1:n // 2] = 2
    else:
        h[1:(n + 1) // 2] = 2
    e = np.abs(np.fft.ifft(X * h))
    w = max(1, int(smooth_ms / 1000 * FS))
    return np.convolve(e, np.ones(w) / w, mode="same")


def xcorr_peak(a, b):
    """decalage (ech.) ou b apparait dans a."""
    n = len(a) + len(b)
    nf = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(a, nf) * np.conj(np.fft.rfft(b, nf)), nf)[:len(a)]
    return int(np.argmax(np.abs(c)))


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-9))


def hit_metrics(seg, src):
    """seg et src alignes sur le debut du kick source (meme longueur)."""
    out = {}
    hf_s, hf_r = band(src, *CLIC_BAND), band(seg, *CLIC_BAND)
    lf_s, lf_r = band(src, *CORPS_BAND), band(seg, *CORPS_BAND)
    eh_s, eh_r = envelope(hf_s, 0.3), envelope(hf_r, 0.3)
    el_s, el_r = envelope(lf_s, 8), envelope(lf_r, 8)

    # arrivee du clic : correlation de l'aigu mesure avec l'aigu source (+-3 ms autour
    # du debut du segment, qui est cale sur le kick large bande), sous l'echantillon
    ref = hf_s[:int(0.012 * FS)]
    span = int(0.003 * FS)
    w = np.concatenate([np.zeros(span), hf_r[:len(ref) + span]])
    c = np.correlate(w, ref, mode="valid")
    k = int(np.argmax(c))
    frac = 0.0
    if 0 < k < len(c) - 1:
        y0, y1, y2 = c[k - 1], c[k], c[k + 1]
        den = y0 - 2 * y1 + y2
        frac = 0.5 * (y0 - y2) / den if den else 0.0
    t_clic = k - span + frac                     # en echantillons, relatif a la source
    out["t_clic_ech"] = float(t_clic)
    ih_s = int(np.argmax(eh_s[:int(0.02 * FS)]))
    ih_r = int(np.clip(round(ih_s + t_clic), 0, len(eh_r) - 1))
    il_s, il_r = int(np.argmax(el_s)), int(np.argmax(el_r))

    def energy(x, a_ms, b_ms, t0):
        a = max(0, int(t0 + a_ms / 1000 * FS)); b = max(a + 1, int(t0 + b_ms / 1000 * FS))
        return float(np.sum(x[a:b] ** 2))
    c0s, c0r = ih_s, ih_r
    E_clic_s, E_clic_r = energy(hf_s, -1, 6, c0s), energy(hf_r, -1, 6, c0r)
    E_corps_s, E_corps_r = energy(lf_s, 0, 300, 0), energy(lf_r, 0, 300, max(0, t_clic))
    # niveau du clic (7 ms autour de son arrivee) relatif a l'energie du corps (300 ms)
    out["clic_rel_db"] = 10 * np.log10(E_clic_r / E_corps_r) - 10 * np.log10(E_clic_s / E_corps_s)

    def width(e, i, drop=10):
        thr = e[i] * 10 ** (-drop / 20)
        a = i
        while a > 0 and e[a] > thr:
            a -= 1
        b = i
        while b < len(e) - 1 and e[b] > thr:
            b += 1
        return (b - a) / FS * 1000
    out["clic_ms"] = width(eh_r, ih_r)
    out["clic_ms_source"] = width(eh_s, ih_s)
    # bavure : aigu qui suit le clic (6-40 ms : reflexions, resonances) / clic lui-meme
    out["bavure_db"] = 10 * np.log10(max(energy(hf_r, 6, 40, c0r), 1e-18) / max(E_clic_r, 1e-18))
    out["bavure_db_source"] = 10 * np.log10(max(energy(hf_s, 6, 40, c0s), 1e-18) / max(E_clic_s, 1e-18))

    # retard du corps : instant ou l'enveloppe du corps atteint -6 dB de son max
    # (front montant), compte depuis le clic, moins le meme ecart dans la source
    def onset(e):
        return int(np.argmax(e >= e.max() * 0.5))
    out["corps_retard_ms"] = ((onset(el_r) - ih_r) - (onset(el_s) - ih_s)) / FS * 1000

    nl_s, nl_r = db(el_s / el_s[il_s]), db(el_r / el_r[il_r])
    a, b = int(0.060 * FS), int(0.300 * FS)
    out["traine_db"] = float(np.mean(nl_r[a:b] - nl_s[a:b]))

    def t20(nl, i):
        j = np.argmax(nl[i:] <= -20)
        return j / FS * 1000 if nl[i + j] <= -20 else None
    out["corps_20db_ms"] = t20(nl_r, il_r)
    out["corps_20db_ms_source"] = t20(nl_s, il_s)
    out["_t_clic"] = ih_r
    out["_env"] = {"clic_src": eh_s, "clic_rec": eh_r, "corps_src": el_s, "corps_rec": el_r,
                   "i_clic_s": ih_s, "i_clic_r": ih_r, "i_corps_s": il_s, "i_corps_r": il_r}
    return out


def analyse(rec_path, label=None):
    """Analyse v3.

    Temps : CamillaDSP ajuste sa frequence en continu, le temps de l'enregistrement
    n'est donc pas une droite parfaite a 20 us pres. Chaque coup est recale sur son
    propre clic. Les mesures de l'aigu (clic, bavure) sont faites coup par coup, en
    energie, bruit de fond soustrait, puis moyennees ; seul le grave (tolerant a
    quelques dizaines de us) est moyenne en forme d'onde.
    """
    rec, _ = read_wav_mono(rec_path, channel=MIC_CHANNEL)
    src = make_kick()
    sch, _ = schedule()
    seg_n = int(0.6 * FS)
    src_pad = np.concatenate([src, np.zeros(seg_n - len(src))])[:seg_n]
    hf_rec, lf_rec = band(rec, *CLIC_BAND), band(rec, *CORPS_BAND)
    hf_src, lf_src = band(src_pad, *CLIC_BAND), band(src_pad, *CORPS_BAND)
    ref_clic = hf_src[:int(0.012 * FS)]

    # 1. calage grossier (premier coup G+D), puis prediction de chaque coup
    t_first = [t for typ, tour, t in sch if typ == "GD"][0]
    lo, hi = int((t_first - 0.2) * FS), int((t_first + 1.2 + KICK_DUR) * FS)
    lag = lo + xcorr_peak(rec[lo:hi], src_pad) - int(t_first * FS)

    def clic_arrival(pred, span_ms):
        """position (ech., flottante) du debut du kick d'apres le clic, autour de pred."""
        span = int(span_ms / 1000 * FS)
        a = pred - span
        w = hf_rec[a:a + len(ref_clic) + 2 * span]
        c = np.correlate(w, ref_clic, mode="valid")
        k = int(np.argmax(c))
        frac = 0.0
        if 0 < k < len(c) - 1:
            y0, y1, y2 = c[k - 1], c[k], c[k + 1]
            den = y0 - 2 * y1 + y2
            frac = 0.5 * (y0 - y2) / den if den else 0.0
        return a + k + frac, float(c[k] / (np.linalg.norm(ref_clic) * np.linalg.norm(w[k:k + len(ref_clic)]) + 1e-18))

    # 2. arrivee de chaque coup, de proche en proche (la derive est lente)
    arrivals, corr, prev_err = [], [], 0.0
    for _, _, t0 in sch:
        pred = int(t0 * FS) + lag + int(round(prev_err))
        t, cc = clic_arrival(pred, 3.0)
        arrivals.append(t)
        corr.append(cc)
        prev_err = t - (int(t0 * FS) + lag)
    arrivals = np.array(arrivals)
    t_nom = np.array([t0 for _, _, t0 in sch])
    coef = np.polyfit(t_nom, arrivals, 1)
    derive_ppm = (coef[0] / FS - 1) * 1e6
    wander_ms = float(np.max(np.abs(arrivals - np.polyval(coef, t_nom))) / FS * 1000)

    # 3. bruit de fond (silence avant le premier coup) : puissance par echantillon
    n0 = int((WARMUP_S - 3.0) * FS) + lag
    pn_hf = float(np.mean(hf_rec[n0:n0 + int(2.0 * FS)] ** 2))
    pn_lf = float(np.mean(lf_rec[n0:n0 + int(2.0 * FS)] ** 2))

    def E(x, t, a_ms, b_ms, pn):
        a, b = int(round(t + a_ms / 1000 * FS)), int(round(t + b_ms / 1000 * FS))
        return max(float(np.sum(x[a:b] ** 2)) - pn * (b - a), 1e-18)

    # source : le kick commence a 0 ; clic de la source au meme repere
    Es_clic = E(hf_src, 0, -1, 6, 0) if False else float(np.sum(hf_src[:int(0.006 * FS)] ** 2))
    Es_late = float(np.sum(hf_src[int(0.006 * FS):int(0.040 * FS)] ** 2)) + 1e-18
    Es_corps = float(np.sum(lf_src[:int(0.300 * FS)] ** 2))

    res = {"etiquette": label, "date": datetime.date.today().isoformat(), "tours": TOURS,
           "derive_horloge_ppm": round(float(derive_ppm), 1),
           "flottement_ms": round(wander_ms, 3),
           "correlation_clic_min": round(float(min(corr)), 2),
           "bruit_clic_dbfs": round(10 * np.log10(pn_hf + 1e-30), 1),
           "types": {}}
    peaks = []
    keys = ["clic_rel_db", "bavure_db", "corps_retard_ms", "traine_db", "corps_20db_ms"]
    avg = {}
    for typ in ORDRE:
        idx = [i for i, (ty, _, _) in enumerate(sch) if ty == typ]
        ec = sum(E(hf_rec, arrivals[i], -1, 6, pn_hf) for i in idx)
        el = sum(E(hf_rec, arrivals[i], 6, 40, pn_hf) for i in idx)
        eb = sum(E(lf_rec, arrivals[i], 0, 300, pn_lf) for i in idx)
        per_clic = [10 * np.log10(E(hf_rec, arrivals[i], -1, 6, pn_hf) / E(lf_rec, arrivals[i], 0, 300, pn_lf))
                    - 10 * np.log10(Es_clic / Es_corps) for i in idx]
        # rapport clic / bruit (clic moyen d'un coup)
        snr = 10 * np.log10((ec / len(idx)) / (pn_hf * int(0.007 * FS)))
        segs = [rec[int(round(arrivals[i])):int(round(arrivals[i])) + seg_n] for i in idx]
        peaks += [db(np.max(np.abs(s))) for s in segs]
        a = np.mean(segs, axis=0)
        avg[typ] = a
        el_s, el_r = envelope(lf_src, 8), envelope(band(a, *CORPS_BAND), 8)
        il_s, il_r = int(np.argmax(el_s)), int(np.argmax(el_r))
        nl_s, nl_r = db(el_s / el_s[il_s]), db(el_r / el_r[il_r])
        aa, bb = int(0.060 * FS), int(0.300 * FS)

        def onset(e):
            return int(np.argmax(e >= e.max() * 0.5))

        def t20(nl, i):
            j = np.argmax(nl[i:] <= -20)
            return j / FS * 1000 if nl[i + j] <= -20 else None
        agg = {
            "clic_rel_db": 10 * np.log10(ec / eb) - 10 * np.log10(Es_clic / Es_corps),
            "clic_rel_db_dispersion": float(np.std(per_clic)),
            "bavure_db": 10 * np.log10(el / ec),
            "bavure_db_source": 10 * np.log10(Es_late / Es_clic),
            "clic_sur_bruit_db": snr,
            "corps_retard_ms": (onset(el_r) - onset(el_s)) / FS * 1000,
            "traine_db": float(np.mean(nl_r[aa:bb] - nl_s[aa:bb])),
            "corps_20db_ms": t20(nl_r, il_r),
            "corps_20db_ms_source": t20(nl_s, il_s),
        }
        agg = {k: (round(float(v), 2) if v is not None else None) for k, v in agg.items()}
        step, n_keep = int(0.0005 * FS), int(0.4 * FS)
        eh_s = envelope(hf_src, 0.3)
        # enveloppe du clic : moyenne des enveloppes (pas des formes d'onde) des coups
        eh_r = np.mean([envelope(hf_rec[int(round(arrivals[i])):int(round(arrivals[i])) + seg_n], 0.3)
                        for i in idx], axis=0)
        g = el_r.max()
        agg["enveloppes"] = {
            "t_ms": [round(i / FS * 1000, 2) for i in range(0, n_keep, step)],
            "clic_src": [round(float(v), 1) for v in db(eh_s[:n_keep] / el_s.max())[::step]],
            "clic_rec": [round(float(v), 1) for v in db(eh_r[:n_keep] / g)[::step]],
            "corps_src": [round(float(v), 1) for v in db(el_s[:n_keep] / el_s.max())[::step]],
            "corps_rec": [round(float(v), 1) for v in db(el_r[:n_keep] / g)[::step]],
        }
        res["types"][typ] = agg
    res["pic_micro_dbfs"] = round(float(max(peaks)), 2)

    # ecart G - D : chaque coup G compare au coup D qui le suit (1 s plus tard)
    d = []
    for tr in range(TOURS):
        iG = [i for i, (ty, t, _) in enumerate(sch) if ty == "G" and t == tr][0]
        iD = [i for i, (ty, t, _) in enumerate(sch) if ty == "D" and t == tr][0]
        d.append(((arrivals[iG] - t_nom[iG] * FS) - (arrivals[iD] - t_nom[iD] * FS)) / FS * 1000)
    res["ecart_GD_ms"] = round(float(np.mean(d)), 3)
    res["ecart_GD_dispersion_ms"] = round(float(np.std(d)), 3)
    res["mesure_suspecte"] = bool(min(corr) < 0.3 or res["ecart_GD_dispersion_ms"] > 0.1)

    # spectre 30-200 Hz des coups moyens
    win = np.hanning(seg_n)
    F = np.fft.rfftfreq(seg_n, 1 / FS)
    m = (F >= 30) & (F <= 200)
    spec = {t: np.abs(np.fft.rfft(avg[t] * win)) for t in ORDRE}
    S_src = np.abs(np.fft.rfft(src_pad * win))
    ref = np.max(spec["GD"][m])
    res["spectre_grave"] = {"f": [round(float(x), 1) for x in F[m]],
                            "src": [round(float(v), 1) for v in db(S_src[m] / S_src[m].max())],
                            **{t: [round(float(v), 1) for v in db(spec[t][m] / ref)] for t in ORDRE},
                            "G+D_en_phase": [round(float(v), 1) for v in db((spec["G"][m] + spec["D"][m]) / ref)]}
    return res


def show(res):
    print(f"Pic micro {res['pic_micro_dbfs']:+.1f} dBFS ; ecart G - D {res['ecart_GD_ms']:+.3f} ms "
          f"(+-{res['ecart_GD_dispersion_ms']:.3f}) ; derive {res['derive_horloge_ppm']} ppm, "
          f"flottement {res['flottement_ms']} ms, correlation clic min {res['correlation_clic_min']}")
    if res["mesure_suspecte"]:
        print("!!! MESURE SUSPECTE : a refaire")
    rows = [("clic_rel_db", "Clic relatif (dB)"), ("clic_rel_db_dispersion", "  dispersion (dB)"),
            ("bavure_db", "Bavure clic (dB)"), ("clic_sur_bruit_db", "Clic / bruit (dB)"),
            ("corps_retard_ms", "Retard corps (ms)"), ("traine_db", "Traine corps (dB)"),
            ("corps_20db_ms", "Chute -20 dB (ms)")]
    print(f"{'':22}" + "".join(f"{t:>10}" for t in ORDRE) + f"{'source':>10}")
    srcv = {"clic_rel_db": 0.0, "bavure_db": res["types"]["GD"]["bavure_db_source"],
            "corps_retard_ms": 0.0, "traine_db": 0.0, "corps_20db_ms": res["types"]["GD"]["corps_20db_ms_source"]}
    for k, name in rows:
        vals = [res["types"][t][k] for t in ORDRE]
        s = srcv.get(k)
        print(f"{name:22}" + "".join(f"{v:>10.2f}" if v is not None else f"{'-':>10}" for v in vals)
              + (f"{s:>10.2f}" if s is not None else f"{'':>10}"))


def save(res):
    d = os.path.join(HERE, "resultats", "kick")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{res['date']}_{res['etiquette']}.json")
    json.dump(res, open(p, "w"))
    print("->", p)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gen":
        gen()
    elif cmd == "mesure":
        label = sys.argv[2]
        rec = f"/tmp/kick2_{label}.wav"
        play_record(rec)
        r = analyse(rec, label); show(r); save(r)
    elif cmd == "analyse":
        r = analyse(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None); show(r)
        if len(sys.argv) > 3:
            save(r)
