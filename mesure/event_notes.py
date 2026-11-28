#!/usr/bin/env python3
"""Notes /10 du reglage de l'event, contre deux references : audiophile et pro.

Seuils dans event_notes.json (modifiables) : pour chaque critere, la valeur
qui vaut 10 ('bon') et celle qui vaut 0 ('mauvais'), interpolation entre les
deux (en log pour la distorsion). Note globale = moyenne ponderee.

Compression et distorsion sont jugees au niveau cible de la reference
(105 dB SPL de crete a la place d'ecoute en audiophile, 115 dB en pro). Pour
convertir un volume CamillaDSP en dB SPL il faut un point de calibration :
--spl VOLUME:SPL, par exemple --spl -30:85 si un sonometre (ou une appli de
telephone, ponderation C, bruit rose) lit 85 dB a la place d'ecoute a -30 dB.
Sans calibration, elles sont jugees au palier le plus fort et c'est signale.

Appele par  event.py analyse <session> [--spl V:SPL]
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

NOMS = {
    "accord_GD_hz": "Accord identique G/D (ecart Hz)",
    "extension_f3_hz": "Extension grave (-3 dB, Hz)",
    "bosse_somme_db": "Bosse de la somme (dB)",
    "retard_groupe_cycles": "Retard de groupe (cycles)",
    "resonance_tuyau_db": "Resonance de tuyau vs woofer (dB)",
    "forme_GD_db": "Forme du grave G/D 30-150 Hz (ecart dB)",
    "compression_db": "Compression au niveau cible (dB)",
    "h3_pct": "H3 au niveau cible (%)",
    "h2_pct": "H2 au niveau cible (%)",
    "niveau_max_propre_db": "Niveau max propre (dB SPL)",
}


def note(v, s):
    if v is None:
        return None
    b, m = s["bon"], s["mauvais"]
    if s.get("log"):
        v, b, m = (math.log10(max(x, 1e-3)) for x in (v, b, m))
    fr = (v - m) / (b - m)
    return round(10 * min(1.0, max(0.0, fr)), 1)


def _interp(paliers, v, cle):
    pts = sorted((p["volume_db"], p.get(cle, 0.0)) for p in paliers)
    for (v1, y1), (v2, y2) in zip(pts, pts[1:]):
        if v1 <= v <= v2:
            return y1 + (y2 - y1) * (v - v1) / (v2 - v1) if v2 > v1 else y2
    return None


def niveau(paliers, spl, cible, propre):
    """Valeurs de compression, H2, H3 au niveau cible, niveau max propre, et remarque."""
    if not paliers:
        return {}, "pas de paliers de niveau (event.py niveaux)"
    haut = max(paliers, key=lambda p: p["volume_db"])
    out, rem = {}, None
    vals = lambda p: {"compression_db": abs(min(0.0, p.get("compression_max_db", 0.0))),
                      "h3_pct": p["h3_max_pct"], "h2_pct": p["h2_max_pct"]}
    if spl is None:
        out.update(vals(haut))
        rem = f"niveau non calibre : juge au palier le plus fort ({haut['volume_db']:g} dB CamillaDSP)"
    else:
        v0, s0 = spl
        v_cible = v0 + (cible - s0)
        if v_cible <= haut["volume_db"]:
            if v_cible < min(p["volume_db"] for p in paliers):
                out.update(vals(min(paliers, key=lambda p: p["volume_db"])))
            else:
                out["compression_db"] = abs(min(0.0, _interp(paliers, v_cible, "compression_max_db") or 0.0))
                out["h3_pct"] = _interp(paliers, v_cible, "h3_max_pct")
                out["h2_pct"] = _interp(paliers, v_cible, "h2_max_pct")
        elif "arret" in haut:
            out.update(vals(haut))
            rem = (f"limite atteinte a {s0 + haut['volume_db'] - v0:.0f} dB SPL, avant la cible "
                   f"{cible} dB ({haut['arret']})")
        else:
            rem = f"paliers trop bas : la cible {cible} dB SPL demande {v_cible:g} dB CamillaDSP"
        ok = [p for p in paliers if abs(min(0.0, p.get("compression_max_db", 0.0))) <= propre["compression_max_db"]
              and p["h3_max_pct"] <= propre["h3_max_pct"]]
        if ok:
            out["niveau_max_propre_db"] = s0 + max(p["volume_db"] for p in ok) - v0
    return out, rem


def valeurs(res, cote, paliers, spl, ref, propre):
    r = res["cotes"][cote]
    v = {
        "accord_GD_hz": abs(res["ecart_fb_GD_hz"]) if "ecart_fb_GD_hz" in res else None,
        "extension_f3_hz": r.get("somme_f3_hz"),
        "bosse_somme_db": r.get("bosse_max_somme_db"),
        "retard_groupe_cycles": (r["retard_groupe_max_ms"] / 1000 * r["retard_groupe_max_a_hz"]
                                 if "retard_groupe_max_ms" in r else None),
        "resonance_tuyau_db": (max((p["vs_woofer_db"] for p in r["resonances_tuyau"] if "vs_woofer_db" in p),
                                   default=-60.0) if "echelle_event_db" in r else None),
        "forme_GD_db": res.get("ecart_forme_GD_30_150_db"),
    }
    n, rem = niveau(paliers, spl, ref["spl_cible_db"], propre)
    v.update({k: n.get(k) for k in ("compression_db", "h3_pct", "h2_pct", "niveau_max_propre_db")})
    return v, rem


def noter(res, paliers_par_cote, spl=None, seuils=None):
    cfg = json.load(open(seuils or os.path.join(HERE, "event_notes.json")))
    sortie = {}
    for nom_ref, ref in cfg["references"].items():
        bloc = {"spl_cible_db": ref["spl_cible_db"], "cotes": {}}
        for cote in res["cotes"]:
            v, rem = valeurs(res, cote, paliers_par_cote.get(cote), spl, ref, cfg["propre"])
            crit = {}
            somme = poids = 0.0
            for k, s in ref["criteres"].items():
                nt = note(v.get(k), s)
                crit[k] = {"valeur": None if v.get(k) is None else round(v[k], 2), "note": nt}
                if nt is not None:
                    somme += nt * s.get("poids", 1); poids += s.get("poids", 1)
            nb = sum(1 for x in crit.values() if x["note"] is not None)
            bloc["cotes"][cote] = {"criteres": crit, "note_globale": round(somme / poids, 1) if poids else None,
                                   "criteres_notes": f"{nb}/{len(crit)}", "remarque_niveau": rem}
        sortie[nom_ref] = bloc
    return sortie


def tableau(notes):
    L = []
    for nom_ref, b in notes.items():
        cotes = list(b["cotes"])
        L += [f"## Notes {nom_ref} (niveau cible {b['spl_cible_db']} dB SPL)", "",
              "| Critere | " + " | ".join(f"{c} valeur | {c} note" for c in cotes) + " |",
              "| --- |" + " --- | --- |" * len(cotes)]
        for k in NOMS:
            cells = []
            for c in cotes:
                x = b["cotes"][c]["criteres"].get(k, {})
                cells += ["-" if x.get("valeur") is None else f"{x['valeur']:g}",
                          "-" if x.get("note") is None else f"{x['note']:g}/10"]
            L.append(f"| {NOMS[k]} | " + " | ".join(cells) + " |")
        L.append("| **Note globale** | " + " | ".join(
            f"{b['cotes'][c]['criteres_notes']} criteres | **{b['cotes'][c]['note_globale']}/10**"
            for c in cotes) + " |")
        for c in cotes:
            if b["cotes"][c]["remarque_niveau"]:
                L.append(f"\n{c} : {b['cotes'][c]['remarque_niveau']}")
        L.append("")
    return "\n".join(L)
