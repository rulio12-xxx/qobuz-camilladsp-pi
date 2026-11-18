import subprocess
import time
from gen_kick import WARMUP_S, N_HITS, HIT_PERIOD_S, TAIL_S, FS

REC_PATH = "/tmp/kick_rec.wav"
DEVICE = "hw:USB,0"


def mpc(*a):
    return subprocess.run(["mpc", *a], capture_output=True, text=True).stdout


total_s = WARMUP_S + N_HITS * HIT_PERIOD_S + TAIL_S

print("Amorcage...")
mpc("clear"); mpc("add", "kick_test.wav"); mpc("play")
time.sleep(total_s + 1.0)
mpc("stop")
time.sleep(0.5)

print("Mesure...")
mpc("clear"); mpc("add", "kick_test.wav")
rec_proc = subprocess.Popen([
    "arecord", "-D", DEVICE, "-f", "S32_LE", "-r", str(FS),
    "-c", "2", "-d", str(int(total_s) + 2), REC_PATH
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.4)
mpc("play")
rec_proc.wait()
mpc("stop")
print("OK, enregistre dans", REC_PATH)
