import json

with open("/home/rulio12/bassmeasure/matrix_results/matrix_results.json") as f:
    data = json.load(f)

LEVELS = [-40, -25, -15, -5, 0]
CHANNELS = ["L", "R"]

# on ne garde que les tons ou le niveau capte est credible (> -45dBFS
# de fondamentale) pour eviter les artefacts de plancher de bruit
MIN_FUND_DBFS = -45.0

print("=== Reponse en frequence relative (dB), zone grave ===\n")
for level in LEVELS:
    for ch in CHANNELS:
        key = f"{level}_{ch}"
        bands = data[key]["sweep"]["bands_rel_db"]
        row = "  ".join(f"{f}Hz:{v:+.1f}" if v is not None else f"{f}Hz:--"
                        for f, v in bands.items() if float(f) <= 200)
        print(f"[{level:+3d}dB {ch}] {row}")
    print()

print("\n=== THD+N grave, tons valides seulement (fondamentale > -45dBFS) ===\n")
for level in LEVELS:
    for ch in CHANNELS:
        key = f"{level}_{ch}"
        thd = data[key]["thd"]
        valid = [r for r in thd if r["fund_dbfs"] > MIN_FUND_DBFS]
        if not valid:
            print(f"[{level:+3d}dB {ch}] aucun ton exploitable")
            continue
        worst = max(valid, key=lambda r: r["thdn_pct"])
        mean_thdn = sum(r["thdn_pct"] for r in valid) / len(valid)
        print(f"[{level:+3d}dB {ch}] {len(valid)}/{len(thd)} tons valides | "
              f"THD+N moyen {mean_thdn:.2f}% | pire {worst['thdn_pct']:.2f}% a {worst['f0_nominal']:.0f}Hz")
