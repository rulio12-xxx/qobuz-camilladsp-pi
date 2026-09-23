import numpy as np
from sweep_dsp import read_wav_mono, find_offset

FS = 44100
N_ITER = 4

print("Decalage direct R vs L (correlation croisee brute, pas de reference separee)\n")
offsets_ms = []
for it in range(1, N_ITER + 1):
    r, _ = read_wav_mono(f"/tmp/it_{it}_R.wav", channel=0)
    l, _ = read_wav_mono(f"/tmp/it_{it}_L.wav", channel=0)

    # find_offset(recorded, marker) cherche 'marker' dans 'recorded' :
    # on cherche R dans L (les deux contiennent le meme sweep de reference)
    off_samples = find_offset(l, r[: int(2.0 * FS)], search_seconds=8.0, fs=FS)
    off_ms = off_samples / FS * 1000.0
    offsets_ms.append(off_ms)
    print(f"Iteration {it} : L en retard de {off_ms:+.2f} ms sur R (decalage brut, large bande)")

print(f"\nMoyenne : {np.mean(offsets_ms):+.2f} ms, ecart-type : {np.std(offsets_ms):.2f} ms")
