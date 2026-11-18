import numpy as np
from sweep_dsp import write_wav

FS = 44100
WARMUP_S = 7.5
TAIL_S = 2.0
N_HITS = 6
HIT_PERIOD_S = 1.0

F_START, F_END = 150.0, 55.0
TAU_PITCH = 0.045
TAU_AMP = 0.22
KICK_DUR = 0.5

CLICK_DUR = 0.004
CLICK_LEVEL = 0.35


def make_kick():
    n = int(KICK_DUR * FS)
    t = np.arange(n) / FS

    pitch = F_END + (F_START - F_END) * np.exp(-t / TAU_PITCH)
    phase = 2 * np.pi * np.cumsum(pitch) / FS
    body_env = np.exp(-t / TAU_AMP)
    body = np.sin(phase) * body_env

    rng = np.random.default_rng(42)
    click_n = int(CLICK_DUR * FS)
    click_env = np.exp(-np.arange(click_n) / (CLICK_DUR * FS / 4))
    click = rng.uniform(-1, 1, click_n) * click_env * CLICK_LEVEL
    click_padded = np.zeros(n)
    click_padded[:click_n] = click

    kick = body + click_padded
    peak = np.max(np.abs(kick))
    kick = kick / peak * 0.9

    fade_n = int(0.002 * FS)
    fade = np.linspace(1.0, 0.0, fade_n)
    kick[-fade_n:] *= fade

    return kick


def main():
    kick = make_kick()
    period_n = int(HIT_PERIOD_S * FS)
    train = np.zeros(period_n * N_HITS)
    for i in range(N_HITS):
        start = i * period_n
        train[start:start + len(kick)] += kick

    lead = np.zeros(int(WARMUP_S * FS))
    tail = np.zeros(int(TAIL_S * FS))
    mono = np.concatenate([lead, train, tail])
    stereo = np.column_stack([mono, mono])
    write_wav("/home/rulio12/musique/kick_test.wav", stereo, FS, channels=2, sampwidth=3)
    total_s = len(mono) / FS
    print(f"OK : kick_test.wav genere, {total_s:.2f}s total, "
          f"{N_HITS} coups espaces de {HIT_PERIOD_S:.1f}s a partir de {WARMUP_S:.1f}s")


if __name__ == "__main__":
    main()
