#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coeur DSP pour la mesure de reponse en frequence par sweep log +
deconvolution frequentielle (methode Farina, sans dependance scipy).

Principe : on joue un sweep sinusoidal logarithmique connu x(t), on
l'enregistre au micro -> y(t). La reponse en frequence du systeme est
H(f) = Y(f) * conj(X(f)) / (|X(f)|^2 + eps). Cette methode est robuste
a un decalage temporel constant (latence de lecture/enregistrement) :
un retard pur ne change que la phase de H(f), jamais son module - donc
la magnitude en dB reste correcte meme sans alignement temporel precis.
"""

import wave
import numpy as np


def generate_log_sweep(f1, f2, duration, fs):
    """Sweep sinusoidal exponentiel (ESS, Farina) de f1 a f2 en `duration` s."""
    n = int(duration * fs)
    t = np.arange(n) / fs
    ln_ratio = np.log(f2 / f1)
    L = duration / ln_ratio
    K = 2 * np.pi * f1 * L
    sweep = np.sin(K * (np.exp(t / L) - 1.0))

    # fenetres de fondu (10 ms) pour eviter les clics au debut/fin
    fade_n = max(1, int(0.01 * fs))
    fade = np.linspace(0.0, 1.0, fade_n)
    sweep[:fade_n] *= fade
    sweep[-fade_n:] *= fade[::-1]

    return sweep.astype(np.float64)


def write_wav(path, samples, fs, channels=2, sampwidth=3):
    """Ecrit un WAV PCM (16/24/32 bits) a partir d'un signal float [-1,1].
    Si channels=2 et samples est 1D, le signal est duplique sur L/R."""
    samples = np.clip(samples, -1.0, 1.0)
    if channels == 2 and samples.ndim == 1:
        samples = np.column_stack([samples, samples])

    if sampwidth == 2:
        ints = (samples * 32767.0).astype("<i2")
        raw = ints.tobytes()
    elif sampwidth == 3:
        ints = np.round(samples * 8388607.0).astype(np.int32)
        raw_i4 = ints.astype("<i4").tobytes()
        # ne garder que les 3 octets bas de chaque entier 32 bits (little endian)
        arr4 = np.frombuffer(raw_i4, dtype=np.uint8).reshape(-1, 4)
        raw = arr4[:, :3].tobytes()
    elif sampwidth == 4:
        ints = (samples * 2147483647.0).astype("<i4")
        raw = ints.tobytes()
    else:
        raise ValueError("sampwidth doit etre 2, 3 ou 4")

    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(fs)
        w.writeframes(raw)


def read_wav_mono(path, channel=None):
    """Lit un WAV (n'importe quel nb de canaux/bits) et retourne
    (signal mono float [-1,1], fs).

    channel=None : moyenne de tous les canaux (pour un signal duplique
    L/R comme nos sweeps/tons generes). channel=0/1/... : ne garde que
    ce canal (indispensable pour un enregistrement ou un seul input du
    Scarlett porte le micro)."""
    with wave.open(path, "rb") as w:
        fs = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(n)

    if sw == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        padded = np.zeros((arr.shape[0], 4), dtype=np.uint8)
        padded[:, :3] = arr
        padded[:, 3] = np.where(arr[:, 2] >= 128, 0xFF, 0x00)  # extension de signe
        data = padded.view("<i4").astype(np.float64).flatten() / 8388608.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"largeur d'echantillon non geree: {sw} octets")

    if ch > 1:
        data = data.reshape(-1, ch)
        data = data[:, channel] if channel is not None else data.mean(axis=1)
    return data, fs


def deconvolve(sweep, recorded, fs, regularization=1e-3):
    """Retourne (freqs, mag_db) : reponse en frequence H(f) en dB.

    `recorded` peut etre plus long que `sweep` (marge de latence/queue de
    reverb) - dans ce cas sweep est complete de zeros a la meme longueur.
    """
    n = len(recorded)
    if len(sweep) > n:
        recorded = np.concatenate([recorded, np.zeros(len(sweep) - n)])
        n = len(sweep)
    sweep_padded = np.concatenate([sweep, np.zeros(n - len(sweep))])

    X = np.fft.rfft(sweep_padded)
    Y = np.fft.rfft(recorded)

    power = np.abs(X) ** 2
    eps = regularization * np.max(power)
    H = (Y * np.conj(X)) / (power + eps)

    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(H)
    mag_db = 20 * np.log10(np.maximum(mag, 1e-12))
    return freqs, mag_db


def blackman_harris(n):
    """Fenetre Blackman-Harris 4 termes (tres faible leakage spectral,
    essentielle pour ne pas polluer la mesure d'harmoniques)."""
    a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
    k = np.arange(n)
    return (a0
            - a1 * np.cos(2 * np.pi * k / (n - 1))
            + a2 * np.cos(4 * np.pi * k / (n - 1))
            - a3 * np.cos(6 * np.pi * k / (n - 1)))


def find_offset(recorded, marker, search_seconds=None, fs=44100):
    """Trouve le decalage (en echantillons) auquel `marker` apparait dans
    `recorded`, par correlation croisee (domaine frequentiel, rapide)."""
    if search_seconds is not None:
        recorded = recorded[: int(search_seconds * fs)]
    n = len(recorded) + len(marker) - 1
    nfft = 1
    while nfft < n:
        nfft *= 2
    R = np.fft.rfft(recorded, nfft)
    M = np.fft.rfft(marker, nfft)
    corr = np.fft.irfft(R * np.conj(M), nfft)
    return int(np.argmax(np.abs(corr[: len(recorded)])))


def analyze_tone(segment, fs, f0_nominal, max_harmonic=9, search_frac=0.02):
    """Analyse un segment de ton pur (deja fenetre en steady-state) :
    retrouve la fondamentale reelle, mesure THD / THD+N / bruit.

    Retourne un dict : f0_detected, fund_dbfs, thd_pct, thd_db, thdn_pct,
    thdn_db, noise_dbfs.
    """
    n = len(segment)
    win = blackman_harris(n)
    # correction de gain de la fenetre (coherent gain) pour retrouver
    # une amplitude correcte
    cg = np.sum(win) / n
    spec = np.fft.rfft(segment * win)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    power = (np.abs(spec) / (n * cg)) ** 2 * 2  # *2 : energie repliee sur le spectre positif
    power[0] /= 2  # DC non double

    bin_hz = fs / n

    def bin_at(f):
        return int(round(f / bin_hz))

    # recherche de la fondamentale reelle pres de f0_nominal (derive d'horloge)
    lo = bin_at(f0_nominal * (1 - search_frac))
    hi = bin_at(f0_nominal * (1 + search_frac)) + 1
    lo, hi = max(1, lo), min(len(power) - 1, hi)
    peak_bin = lo + int(np.argmax(power[lo:hi]))
    f0_detected = peak_bin * bin_hz

    # largeur du lobe principal d'une fenetre Blackman-Harris 4 termes :
    # ~ +-4 bins ; on prend une marge de securite a +-6.
    LOBE_HALF_WIDTH = 6

    def band_power(center_bin, half_width=LOBE_HALF_WIDTH):
        a = max(0, center_bin - half_width)
        b = min(len(power), center_bin + half_width + 1)
        return float(np.sum(power[a:b]))

    fund_power = band_power(peak_bin)

    harmonics_power = 0.0
    excluded = np.zeros(len(power), dtype=bool)
    a, b = max(0, peak_bin - LOBE_HALF_WIDTH), min(len(power), peak_bin + LOBE_HALF_WIDTH + 1)
    excluded[a:b] = True
    nyquist = fs / 2
    for h in range(2, max_harmonic + 1):
        fh = f0_detected * h
        if fh >= nyquist * 0.98:
            break
        hb = bin_at(fh)
        harmonics_power += band_power(hb)
        a, b = max(0, hb - LOBE_HALF_WIDTH), min(len(power), hb + LOBE_HALF_WIDTH + 1)
        excluded[a:b] = True

    total_power = float(np.sum(power[1:]))  # hors DC
    noise_power = max(0.0, float(np.sum(power[1:][~excluded[1:]])))

    def to_db(p):
        return 10 * np.log10(max(p, 1e-24))

    thd_ratio = np.sqrt(harmonics_power / fund_power) if fund_power > 0 else float("inf")
    thdn_ratio = np.sqrt((harmonics_power + noise_power) / fund_power) if fund_power > 0 else float("inf")

    return {
        "f0_nominal": f0_nominal,
        "f0_detected": f0_detected,
        "fund_dbfs": to_db(fund_power) / 2,
        "thd_pct": thd_ratio * 100,
        "thd_db": 20 * np.log10(max(thd_ratio, 1e-12)),
        "thdn_pct": thdn_ratio * 100,
        "thdn_db": 20 * np.log10(max(thdn_ratio, 1e-12)),
        "noise_dbfs": to_db(noise_power) / 2,
    }


def deconvolve_complex(sweep, recorded, fs, regularization=1e-3):
    """Comme deconvolve(), mais retourne H(f) complexe (magnitude + phase),
    necessaire pour calculer un delai de groupe."""
    n = len(recorded)
    if len(sweep) > n:
        recorded = np.concatenate([recorded, np.zeros(len(sweep) - n)])
        n = len(sweep)
    sweep_padded = np.concatenate([sweep, np.zeros(n - len(sweep))])

    X = np.fft.rfft(sweep_padded)
    Y = np.fft.rfft(recorded)

    power = np.abs(X) ** 2
    eps = regularization * np.max(power)
    H = (Y * np.conj(X)) / (power + eps)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    return freqs, H


def group_delay_at(freqs, H, target_freqs, half_span_hz=20.0):
    """Delai de groupe (ms) de H(f) autour de chaque frequence cible,
    par difference finie de la phase deroulee : tau = -dphi/domega.

    Le deroulement de phase est fait LOCALEMENT (juste sur la fenetre
    autour de f0), pas sur tout le spectre : un deroulement global serait
    contamine par le bruit de phase erratique en dessous de ~40Hz (zone
    ou le systeme n'a quasiment pas d'energie reelle, cf. mesures THD+N)
    qui se propagerait a toutes les frequences superieures."""
    out = {}
    for f0 in target_freqs:
        lo = np.searchsorted(freqs, f0 - half_span_hz)
        hi = np.searchsorted(freqs, f0 + half_span_hz)
        if hi - lo < 2:
            out[f0] = None
            continue
        fx = freqs[lo:hi]
        ph = np.unwrap(np.angle(H[lo:hi]))  # deroulement local uniquement
        slope = np.polyfit(fx, ph, 1)[0]  # rad par Hz
        tau_s = -slope / (2 * np.pi)
        out[f0] = tau_s * 1000.0  # ms
    return out


def band_average_db(freqs, mag_db, centers, frac_octave=1 / 3):
    """Moyenne (en puissance) de mag_db autour de chaque frequence centrale,
    sur une largeur de +-frac_octave/2 octave."""
    out = {}
    for fc in centers:
        lo = fc * (2 ** (-frac_octave / 2))
        hi = fc * (2 ** (frac_octave / 2))
        mask = (freqs >= lo) & (freqs <= hi)
        if not np.any(mask):
            out[fc] = None
            continue
        lin = 10 ** (mag_db[mask] / 20.0)
        rms = np.sqrt(np.mean(lin ** 2))
        out[fc] = 20 * np.log10(rms) if rms > 0 else None
    return out
