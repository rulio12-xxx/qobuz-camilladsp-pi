import json
import numpy as np
from sweep_dsp import read_wav_mono, find_offset
from gen_kick import make_kick, FS, WARMUP_S, KICK_DUR, TAIL_S, HIT_PERIOD_S, N_HITS

MIC_CHANNEL = 0
REC_PATH = "/tmp/kick_rec.wav"
HIT_INDEX = N_HITS - 1  # dernier coup, le plus stable


def envelope(x, win):
    n = len(x) // win
    x = x[: n * win]
    rms = np.sqrt(np.mean(x.reshape(n, win) ** 2, axis=1))
    return rms


def bandpass_fft(x, fs, lo, hi):
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
    mask = (freqs >= lo) & (freqs <= hi)
    Xf = np.where(mask, X, 0)
    return np.fft.irfft(Xf, n=len(x))


def decay_time_db(env, win_s, drop_db=20.0):
    peak = env.max()
    if peak <= 0:
        return None
    target = peak * (10 ** (-drop_db / 20.0))
    idx_peak = np.argmax(env)
    for i in range(idx_peak, len(env)):
        if env[i] <= target:
            return (i - idx_peak) * win_s * 1000.0
    return None


recorded, _ = read_wav_mono(REC_PATH, channel=MIC_CHANNEL)
kick = make_kick()

expected_center = WARMUP_S + HIT_INDEX * HIT_PERIOD_S
# La lecture demarre ~0.4-0.6 s apres arecord (attente + latence MPD/CamillaDSP) :
# fenetre decalee vers l apres pour ne jamais rater le coup.
search_lo = int((expected_center - 0.2) * FS)
search_hi = int((expected_center + 0.9 + KICK_DUR) * FS)
window = recorded[search_lo:search_hi]
local_off = find_offset(window, kick, fs=FS)
offset = search_lo + local_off
print(f"Coup {HIT_INDEX+1}/{N_HITS} localise a {offset/FS:.3f}s "
      f"(attendu ~{expected_center:.2f}s)")

SEG_S = KICK_DUR + TAIL_S
seg_n = int(SEG_S * FS)
rec_seg = recorded[offset: offset + seg_n]
if len(rec_seg) < seg_n:
    rec_seg = np.concatenate([rec_seg, np.zeros(seg_n - len(rec_seg))])
src_seg = np.concatenate([kick, np.zeros(max(0, seg_n - len(kick)))])[:seg_n]

peak_dbfs = 20 * np.log10(np.max(np.abs(rec_seg)))
print(f"Pic du coup analyse : {peak_dbfs:+.1f} dBFS")

WIN = int(0.002 * FS)
env_src = envelope(src_seg, WIN)
env_rec = envelope(rec_seg, WIN)
env_src_db = 20 * np.log10(np.maximum(env_src / env_src.max(), 1e-6))
env_rec_db = 20 * np.log10(np.maximum(env_rec / env_rec.max(), 1e-6))

src_lf = bandpass_fft(src_seg, FS, 40, 120)
rec_lf = bandpass_fft(rec_seg, FS, 40, 120)
env_src_lf = envelope(src_lf, WIN)
env_rec_lf = envelope(rec_lf, WIN)

decay_src = decay_time_db(env_src_lf, WIN / FS, 20.0)
decay_rec = decay_time_db(env_rec_lf, WIN / FS, 20.0)

print(f"\nDecroissance -20dB (bande 40-120Hz) :")
print(f"  Source : {decay_src:.0f} ms" if decay_src else "  Source : non atteinte")
print(f"  Mesure : {decay_rec:.0f} ms" if decay_rec else "  Mesure : non atteinte")

out = {
    "t_ms": (np.arange(len(env_src)) * WIN / FS * 1000.0).tolist(),
    "env_src_db": env_src_db.tolist(),
    "env_rec_db": env_rec_db.tolist(),
    "env_src_lf": (env_src_lf / env_src_lf.max()).tolist(),
    "env_rec_lf": (env_rec_lf / env_src_lf.max()).tolist(),
    "decay_src_ms": decay_src,
    "decay_rec_ms": decay_rec,
    "peak_dbfs": peak_dbfs,
}
with open("/tmp/kick_compare.json", "w") as f:
    json.dump(out, f)
print("\nOK -> /tmp/kick_compare.json")
