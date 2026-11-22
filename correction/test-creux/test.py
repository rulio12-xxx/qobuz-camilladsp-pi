"""Effet calcule d un changement de filtres sur la mesure k0_origine (reponse actuelle).

    python3 correction/test-creux/test.py '{"filtre.param": valeur}' '[[voie, nom, freq, gain, q], ["remove", voie, nom]]' [sortie.yml]
"""
import json, copy, os, sys
import numpy as np, yaml
M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mesure"); sys.path.insert(0, M)
from ir2 import apply_change, responses, FS
import ir2
C = np.array(ir2.CENTERS)
cur = yaml.safe_load(open(os.path.join(M, "..", "camilladsp", "camilladsp-qobuz.yml")))
res = {}
for lab in ["k0_origine", "k0_origine"]:
    pass
z = np.load(M + "/resultats/ir/k0_origine.npz"); meta = json.load(open(M + "/resultats/ir/k0_origine.json"))
irs = {"L": z["L"], "R": z["R"]}
k0 = meta["config"]
def pk(f, g, q): return {"type": "Biquad", "parameters": {"type": "Peaking", "freq": f, "gain": g, "q": q}}
def build(changes, add):
    c = copy.deepcopy(cur)
    for k, v in changes.items():
        n, p = k.split("."); c["filters"][n]["parameters"][p] = v
    for item in add:
        if item[0] == "remove":
            st = [s for s in c["pipeline"] if s.get("type") == "Filter" and s.get("channels") == [item[1]]][0]
            st["names"].remove(item[2]); continue
        ch, name, f, g, q = item
        c["filters"][name] = pk(f, g, q)
        st = [s for s in c["pipeline"] if s.get("type") == "Filter" and s.get("channels") == [ch]][0]
        st["names"].insert(st["names"].index("delay_L" if ch == 0 else "delay_R"), name)
    return c
CHANGES = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
ADD = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
base = responses(apply_change(irs, k0, cur))
new = responses(apply_change(irs, k0, build(CHANGES, ADD)))
sel = (C >= 35) & (C <= 320)
print(" freq |  L act  L test |  R act  R test | G+D act G+D test")
for i in np.where(sel)[0]:
    print(f"{C[i]:6.1f} | {base['L'][i]:6.1f} {new['L'][i]:6.1f} | {base['R'][i]:6.1f} {new['R'][i]:6.1f} | {base['GD'][i]:6.1f} {new['GD'][i]:6.1f}")
b = (C >= 40) & (C <= 300)
for k in "L", "R", "GD":
    print(k, "ecart-type 40-300 Hz : actuel %.1f  test %.1f" % (np.nanstd(base[k][b]), np.nanstd(new[k][b])))
if len(sys.argv) > 3:
    yaml.safe_dump(build(CHANGES, ADD), open(sys.argv[3], "w"), sort_keys=False, allow_unicode=True)
