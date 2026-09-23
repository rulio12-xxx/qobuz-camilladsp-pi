import subprocess
import numpy as np
from sweep_dsp import read_wav_mono

FS = 44100
DUR = 6
DEVICE = "hw:3,0"
REC = "/tmp/ambient_check.wav"

subprocess.run(["arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
                "-c", "2", "-d", str(DUR), REC], capture_output=True)

sig, _ = read_wav_mono(REC, channel=0)
n = len(sig)
win = np.hanning(n)
spec = np.abs(np.fft.rfft(sig * win))
freqs = np.fft.rfftfreq(n, d=1.0/FS)

def band_rms_db(f_lo, f_hi):
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    if not np.any(mask):
        return None
    return 20*np.log10(max(np.sqrt(np.mean(spec[mask]**2)), 1e-9))

overall = 20*np.log10(max(np.sqrt(np.mean(spec**2)), 1e-9))

print(f"Niveau ambiant global : {overall:+.1f} dB (ref arbitraire)\n")
print("Bandes etroites autour des harmoniques secteur (50/100/150Hz) vs voisinage large :")
for f0 in (50, 100, 150):
    narrow = band_rms_db(f0-1.5, f0+1.5)
    wide = band_rms_db(f0-15, f0+15)
    peak_to_floor = narrow - wide if (narrow is not None and wide is not None) else None
    flag = ""
    if peak_to_floor is not None and peak_to_floor > 6:
        flag = "  <-- pic net et etroit, evoque un ronflement secteur"
    print(f"  {f0:>4}Hz : bande etroite {narrow:+.1f} dB, voisinage large {wide:+.1f} dB, "
          f"ecart {peak_to_floor:+.1f} dB{flag}")

# recherche du plus haut pic global sous 300Hz
mask = (freqs >= 15) & (freqs <= 300)
idx = np.argmax(spec[mask])
peak_freq = freqs[mask][idx]
print(f"\nPic le plus fort entre 15-300Hz : {peak_freq:.1f} Hz")
