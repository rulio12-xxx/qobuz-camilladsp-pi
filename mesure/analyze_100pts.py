import json
import numpy as np
from sweep_dsp import generate_log_sweep, read_wav_mono, deconvolve, band_average_db

FS = 44100
SWEEP_DUR = 8.0
MIC_CHANNEL = 0
FMIN, FMAX, NPTS = 20.0, 16000.0, 100

sweep = generate_log_sweep(20, 20000, SWEEP_DUR, FS)

def analyze(path):
    recorded, _ = read_wav_mono(path, channel=MIC_CHANNEL)
    freqs, mag_db = deconvolve(sweep, recorded, FS)
    return freqs, mag_db

fL, mL = analyze("/tmp/bass_L.wav")
fR, mR = analyze("/tmp/bass_R.wav")

targets = np.logspace(np.log10(FMIN), np.log10(FMAX), NPTS)

bandsL = band_average_db(fL, mL, targets, frac_octave=1/6)
bandsR = band_average_db(fR, mR, targets, frac_octave=1/6)
valsL = np.array([bandsL[f] for f in targets])
valsR = np.array([bandsR[f] for f in targets])

def ref_200_1000(freqs, vals):
    mask = (targets >= 200) & (targets <= 1000)
    return vals[mask].mean()

refL = ref_200_1000(targets, valsL)
refR = ref_200_1000(targets, valsR)
relL = valsL - refL
relR = valsR - refR
relMean = (relL + relR) / 2

out = {
    "freqs": targets.tolist(),
    "L": relL.tolist(),
    "R": relR.tolist(),
    "mean": relMean.tolist(),
}
with open("/tmp/curve_100pts.json", "w") as f:
    json.dump(out, f)

print("OK, 100 points generes -> /tmp/curve_100pts.json")
print(f"{'Hz':>7}  {'L':>6}  {'R':>6}  {'moy':>6}")
for i in range(0, NPTS, 5):
    print(f"{targets[i]:>7.0f}  {relL[i]:>+5.1f}  {relR[i]:>+5.1f}  {relMean[i]:>+5.1f}")
