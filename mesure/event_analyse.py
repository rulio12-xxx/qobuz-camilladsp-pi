#!/usr/bin/env python3
"""Analyse numerique de l'event bass-reflex (mesures en champ proche).

Appele par event.py (mesures faites sur le Pi). Lit aussi un fichier REW .mdat (File > Save all measurements) ou des exports
texte REW (File > Export > Measurement as text). Les mesures sont reconnues
par leur nom : "woofer G", "event G", "bruit G" (et G2, "event G b"...), idem D.

Sorties (dans --out) : resume.md, resultats.json, et pour chaque cote :
  evt_<cote>_reponses.png  woofer, event, somme, bruit
  evt_<cote>_retard.png    retard de groupe de la somme
  evt_<cote>_tuyau.png     event 60-2000 Hz avec les resonances detectees
  evt_comparaison_GD.png   gauche contre droite (somme)

Exemple :
  python3 analyse_event.py event-2026-11-28.mdat --out resultats \
      --d-membrane 330 --d-event 100 --l-event 250 --n-event 1 --vb 180

Dependances : numpy, matplotlib, javaobj-py3 (seulement pour les .mdat).
"""
import argparse, json, math, os, re, sys
import numpy as np

C_SON = 343.0  # m/s a ~20 degres

# ---------------------------------------------------------------- lecture
def lire_mdat(path):
    import javaobj.v2 as jv
    objs = jv.loads(open(path, 'rb').read())
    res = {}
    for o in objs:
        cd = getattr(o, 'classdesc', None)
        if not cd or cd.name != 'roomeqwizard.MeasData':
            continue
        F = {}
        for _, fields in o.field_data.items():
            for k, v in fields.items():
                F[k.name] = v
        spl = np.array(list(F['splValues']), float)
        ph = np.array(list(F['phaseValues']), float) if F.get('phaseValues') else None
        if F.get('isLogSpaced'):
            f = F['startFreq'] * 2 ** (np.arange(len(spl)) * float(F['logStep'])) \
                if F.get('logStep') else None
        else:
            f = F['startFreq'] + F['freqStep'] * np.arange(len(spl))
        nom = str(F['shortDesc']).strip()
        res[nom] = dict(f=f, spl=spl, phase=ph, notes=str(F.get('measNotes', '')))
    return res

def lire_txt(path):
    f, s, p = [], [], []
    for ligne in open(path, encoding='utf-8', errors='replace'):
        ligne = ligne.strip()
        if not ligne or ligne[0] in '*#' or not (ligne[0].isdigit()):
            continue
        parts = re.split(r'[\s;]+', ligne.replace(',', '.'))
        try:
            vals = [float(x) for x in parts[:3]]
        except ValueError:
            continue
        f.append(vals[0]); s.append(vals[1]); p.append(vals[2] if len(vals) > 2 else np.nan)
    nom = os.path.splitext(os.path.basename(path))[0].replace('_', ' ')
    p = np.array(p)
    return {nom: dict(f=np.array(f), spl=np.array(s), phase=None if np.all(np.isnan(p)) else p, notes='')}

def charger(paths):
    tout = {}
    for p in paths:
        tout.update(lire_mdat(p) if p.lower().endswith('.mdat') else lire_txt(p))
    return tout

def trouver(mesures, type_, cote):
    """Retourne la liste des noms correspondant a type_ (woofer/event/bruit) et cote (G/D)."""
    pat = re.compile(r'^\s*%s\w*\s+%s\s*(\d*)\s*([a-z]?)\s*$' % (type_, cote), re.I)
    return sorted(n for n in mesures if pat.match(n))

# ---------------------------------------------------------------- outils
FGRID = 2 ** np.arange(math.log2(10), math.log2(2000), 1 / 96)   # 1/96 octave

def complexe(m, grille=FGRID):
    """Interpole module et phase deroulee sur la grille log."""
    f, spl = m['f'], m['spl']
    mag = 10 ** (np.interp(grille, f, spl) / 20)
    if m['phase'] is None:
        return mag, None
    ph = np.unwrap(np.deg2rad(m['phase']))
    return mag * np.exp(1j * np.interp(grille, f, ph)), True

def phase_minimale(mag, grille=FGRID):
    """Phase minimale par Hilbert sur une grille lineaire (si pas de phase mesuree)."""
    n = 2 ** 16; fs = 48000
    fl = np.linspace(0, fs / 2, n // 2 + 1)
    lm = np.log(np.maximum(np.interp(fl, grille, mag, left=mag[0], right=mag[-1]), 1e-9))
    spec = np.concatenate([lm, lm[-2:0:-1]])
    cep = np.fft.ifft(spec).real
    w = np.zeros(n); w[0] = 1; w[1:n // 2] = 2; w[n // 2] = 1
    phm = np.fft.fft(cep * w).imag[:n // 2 + 1]
    return mag * np.exp(1j * np.interp(grille, fl, phm))

def lisser(db, frac=24):
    """Lissage glissant en 1/frac octave sur la grille 1/96 octave."""
    k = max(1, int(96 / frac))
    return np.convolve(np.pad(db, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]

def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-12))

def extremum_affine(f, y, i):
    """Raffinement parabolique en log(f) autour de l'indice i."""
    if 0 < i < len(y) - 1:
        a, b, c = y[i - 1], y[i], y[i + 1]
        den = a - 2 * b + c
        d = 0.5 * (a - c) / den if den != 0 else 0
        return float(f[i] * 2 ** (d / 96)), float(b - 0.25 * (a - c) * d)
    return float(f[i]), float(y[i])

def creux_principal(y, demi=48):
    """Indice du creux le plus marque : profondeur par rapport au plus bas des deux
    maxima situes a +-1/2 octave (un bord de bande descendant ne compte pas)."""
    best, ib = -1e9, int(np.argmin(y))
    for i in range(demi, len(y) - demi):
        if y[i] <= y[i - 1] and y[i] <= y[i + 1]:
            prof = min(np.max(y[i - demi:i]), np.max(y[i + 1:i + demi + 1])) - y[i]
            if prof > best: best, ib = prof, i
    return ib

def bande(f, y, i0, chute):
    ref = y[i0]; lo = i0; hi = i0
    while lo > 0 and y[lo] > ref - chute: lo -= 1
    while hi < len(y) - 1 and y[hi] > ref - chute: hi += 1
    return float(f[lo]), float(f[hi])

# ---------------------------------------------------------------- theorie
REMPLISSAGE = {'aucun': 1.00, 'parois': 1.05, 'partiel': 1.10, 'plein': 1.15}
# volume apparent : un rembourrage rend la compression de l'air plus isotherme
# (ordre de grandeur classique : jusqu'a +15 % environ caisse pleine)

def theorie(a):
    """Accord theorique. Event a bords arrondis : --l-event = longueur TOTALE bord a bord,
    --rayon-bords = rayon des arrondis (mm), --bords-arrondis = 0, 1 ou 2 extremites.
    La masse d'air est integree le long du profil (section qui s'evase dans les arrondis),
    puis la correction d'extremite est appliquee sur le rayon de sortie evase."""
    if not (a.d_event and a.l_event and a.vb):
        return None
    n = a.n_event
    if a.d_event2:   # event rectangulaire : largeur x hauteur -> diametre equivalent
        sp1 = a.d_event * a.d_event2 * 1e-6
        d_eq = 2 * math.sqrt(sp1 / math.pi)
    else:
        d_eq = a.d_event / 1000; sp1 = math.pi * d_eq ** 2 / 4
    sp = n * sp1
    a0 = d_eq / 2
    lt = a.l_event / 1000
    r = (a.rayon_bords or 0) / 1000
    nb = a.bords_arrondis if r > 0 else 0
    if 2 * r * nb / 2 > lt:
        r = lt / max(nb, 1)
    # longueur equivalente (rapportee a la section droite) : integrale de S0/S(x)
    m = 2000
    def l_arrondi():
        x = (np.arange(m) + 0.5) / m * r                      # 0 = plan de sortie
        ax = a0 + r - np.sqrt(np.maximum(r ** 2 - (r - x) ** 2, 0))
        return float(np.sum((a0 / ax) ** 2) * r / m)
    l_eq = (lt - nb * r) + nb * (l_arrondi() if nb else 0)
    # corrections d'extremite : 0,85 a si colle a un panneau, 0,61 a si libre,
    # sur le rayon de sortie (evase s'il y a un arrondi), ramenees a la section droite
    coef = {'2bords': (0.85, 0.85), '1bord': (0.85, 0.61), 'libre': (0.61, 0.61)}[a.terminaisons]
    corr = 0.0
    for i_ext, c in enumerate(coef):
        am = a0 + r if i_ext < nb else a0
        corr += c * am * (a0 / am) ** 2
    leff = l_eq + corr
    vb_net = (a.vb - a.vd_litres) / 1000
    fac = REMPLISSAGE[a.remplissage]
    vb = vb_net * fac
    fb = C_SON / (2 * math.pi) * math.sqrt(sp / (vb * leff))
    l_tuyau = lt + sum(c * (a0 + r if i < nb else a0) for i, c in enumerate(coef))
    tuyau = [k * C_SON / (2 * l_tuyau) for k in (1, 2, 3)]
    out = dict(fb_theorique_hz=round(fb, 1), longueur_effective_mm=round(leff * 1000),
               longueur_totale_mm=round(lt * 1000), rayon_bords_mm=round(r * 1000), bords_arrondis=nb,
               surface_event_cm2=round(sp * 1e4, 1), volume_net_l=round(vb_net * 1000, 1),
               remplissage=a.remplissage, volume_apparent_l=round(vb * 1000, 1),
               resonances_tuyau_prevues_hz=[round(x) for x in tuyau], avertissements=[])
    if a.dist_mousse is not None and a.dist_mousse < a.d_event:
        out['avertissements'].append(
            'Rembourrage a %.0f mm de l entree interieure de l event (< 1 diametre) : '
            'il freine l event, Fb et le niveau peuvent baisser' % a.dist_mousse)
    if a.remplissage in ('partiel', 'plein') and a.dist_mousse is None:
        out['avertissements'].append('Remplissage %s : preciser --dist-mousse (mm)' % a.remplissage)
    return out

# ---------------------------------------------------------------- analyse d'un cote
def _plt():
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None

def analyser_cote(mes, cote, a, out):
    plt = _plt()
    nw, ne, nb = trouver(mes, 'woofer', cote), trouver(mes, 'event', cote), trouver(mes, 'bruit', cote)
    if not nw or not ne:
        return None
    R = dict(cote=cote, mesures_woofer=nw, mesures_event=ne, avertissements=[])
    zone = (FGRID > 12) & (FGRID < 120)
    fz = FGRID[zone]

    # Woofer : creux = Fb (et repetabilite entre woofer G et woofer G2)
    fbs = []
    W = None
    for n in nw:
        w, okph = complexe(mes[n])
        y = lisser(db(w), 48)[zone]
        fbs.append(extremum_affine(fz, y, creux_principal(y))[0])
        if W is None: W, phw = w, okph
    fb = fbs[0]
    R['fb_creux_woofer_hz'] = round(fb, 1)
    if len(fbs) > 1:
        R['fb_repetabilite_hz'] = round(max(fbs) - min(fbs), 2)
        if R['fb_repetabilite_hz'] > 1:
            R['avertissements'].append('Creux du woofer differe de %.1f Hz entre repetitions' % R['fb_repetabilite_hz'])
    yW = lisser(db(W), 48)
    i_fb = int(np.argmin(abs(FGRID - fb)))
    R['profondeur_creux_db'] = round(float(np.max(yW[(FGRID > fb * 1.5) & (FGRID < fb * 3)]) - yW[i_fb]), 1)

    # Event(s) : on prend la mesure principale de chaque event (sans chiffre de repetition)
    principaux = [n for n in ne if not re.search(r'\d\s*$', n)] or ne[:1]
    E_list = []
    for n in principaux:
        e, okph = complexe(mes[n]); E_list.append((n, e, okph))
    n0, E, phe = E_list[0]
    yE = lisser(db(E), 48)
    ze = (FGRID > 12) & (FGRID < 150)
    ip = int(np.argmax(np.where(ze, yE, -1e9)))
    fpk, lpk = extremum_affine(FGRID, yE, ip)
    R['pic_event_hz'] = round(fpk, 1)
    R['ecart_pic_event_creux_woofer_hz'] = round(fpk - fb, 1)
    R['bande_event_3db_hz'] = [round(x, 1) for x in bande(FGRID, yE, ip, 3)]
    R['bande_event_6db_hz'] = [round(x, 1) for x in bande(FGRID, yE, ip, 6)]
    for n in ne:
        if n != n0 and re.match(re.escape(n0) + r'\s*\d', n):
            e2, _ = complexe(mes[n])
            y2 = lisser(db(e2), 48)
            i2 = int(np.argmax(np.where(ze, y2, -1e9)))
            R['pic_event_repetition_hz'] = round(extremum_affine(FGRID, y2, i2)[0], 1)

    # Resonances de tuyau : pics de l'event au-dessus d'une tendance lissee en 1/2 octave
    zt = (FGRID > max(80, 2.5 * fb)) & (FGRID < 2000)
    brut = lisser(db(E), 48)
    tend = lisser(db(E), 2)
    ecart = (brut - tend)
    pics = []
    idx = np.where(zt)[0]
    for i in idx[1:-1]:
        if ecart[i] > 3 and ecart[i] >= ecart[i - 1] and ecart[i] >= ecart[i + 1]:
            if not pics or FGRID[i] > pics[-1][0] * 2 ** (1 / 6):
                pics.append((float(FGRID[i]), float(ecart[i]), float(brut[i] - lpk)))
    R['resonances_tuyau'] = [dict(f_hz=round(f), hauteur_db=round(h, 1), niveau_vs_pic_accord_db=round(l, 1))
                             for f, h, l in pics]

    # Somme woofer + events (Keele : event mis a l'echelle par le rapport des rayons)
    if a.d_membrane and a.d_event:
        d_ev = a.d_event if not a.d_event2 else 2 * math.sqrt(a.d_event * a.d_event2 / math.pi)
        k = d_ev / a.d_membrane
        R['echelle_event_db'] = round(20 * math.log10(k), 2)
    else:
        k = None
        R['avertissements'].append('Diametres non fournis : somme non calculee (donner --d-membrane et --d-event)')
    if k:
        yWl = lisser(db(W), 48)
        for p_ in R['resonances_tuyau']:
            j = int(np.argmin(abs(FGRID - p_['f_hz'])))
            p_['vs_woofer_db'] = round(float(brut[j] + 20 * math.log10(k) - yWl[j]), 1)
    S = None
    if k:
        utilise_minph = a.phase_minimale or not (phw and all(o for _, _, o in E_list))
        if utilise_minph:
            R['methode_somme'] = 'phase minimale (reconstruite a partir du module)'
            Wc = phase_minimale(np.abs(W))
            Es = [phase_minimale(np.abs(e)) for _, e, _ in E_list]
            # le debit de l'event est en opposition avec la membrane sous l'accord
            S = Wc - k * sum(Es) if a.signe_event == 'auto' else Wc + (1 if a.signe_event == '+' else -1) * k * sum(Es)
        else:
            R['methode_somme'] = 'phase mesuree (reference de temps commune)'
            Es = [e for _, e, _ in E_list]
            S = W + k * sum(Es)
        yS = lisser(db(S), 24)
        ref = float(np.mean(yS[(FGRID > 3 * fb) & (FGRID < 200)]))
        def f_sous(n):
            j = np.where((yS - ref < -n) & (FGRID < 3 * fb))[0]
            return round(float(FGRID[j[-1]]), 1) if len(j) else None
        R['somme_f3_hz'], R['somme_f6_hz'], R['somme_f10_hz'] = f_sous(3), f_sous(6), f_sous(10)
        i1, i2 = np.argmin(abs(FGRID - fb / 2)), np.argmin(abs(FGRID - fb / 4))
        if FGRID[i2] >= FGRID[0]:
            R['pente_sous_accord_db_oct'] = round(float(yS[i1] - yS[i2]) / 1.0, 1)
        R['bosse_max_somme_db'] = round(float(np.max(yS[(FGRID > fb) & (FGRID < 200)]) - ref), 1)
        ph = np.unwrap(np.angle(S))
        gd = -np.gradient(ph, 2 * np.pi * FGRID) * 1000
        gd = lisser(gd, 12)
        gd = gd - float(np.median(gd[(FGRID > 300) & (FGRID < 600)]))  # retard en plus de celui du medium
        zg = (FGRID > 15) & (FGRID < 300)
        R['retard_groupe_max_ms'] = round(float(np.max(gd[zg])), 1)
        R['retard_groupe_max_a_hz'] = round(float(FGRID[zg][np.argmax(gd[zg])]), 1)
        R['retard_groupe_a_fb_ms'] = round(float(gd[i_fb]), 1)

    # Bruit
    if nb:
        B, _ = complexe(mes[nb[0]])
        yB = lisser(db(B), 24)
        snr = lisser(db(E), 24) - yB
        mauvais = FGRID[(snr < 10) & (FGRID > 15) & (FGRID < 1000)]
        if len(mauvais):
            R['avertissements'].append('Event moins de 10 dB au-dessus du bruit entre %.0f et %.0f Hz'
                                       % (mauvais.min(), mauvais.max()))
    else:
        yB = None

    # Graphiques (si matplotlib est installe)
    if plt is not None:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.semilogx(FGRID, lisser(db(W), 48), label='woofer (champ proche)', color='#1f6fb4')
        for n, e, _ in E_list:
            ax.semilogx(FGRID, lisser(db(e), 48), label=n + ' (champ proche, niveau brut)', color='#d9822b')
        if S is not None:
            ax.semilogx(FGRID, lisser(db(S), 24), label='somme woofer + event', color='#222', lw=2)
        if yB is not None:
            ax.semilogx(FGRID, yB, label='bruit de fond', color='#999', ls=':')
        ax.axvline(fb, color='#1f6fb4', ls='--', lw=0.8); ax.text(fb, ax.get_ylim()[1] - 3, ' Fb %.1f Hz' % fb)
        for p in R['resonances_tuyau']:
            ax.axvline(p['f_hz'], color='#d9822b', ls=':', lw=0.8)
        ax.set_xlim(10, 2000); ax.grid(True, which='both', alpha=0.3)
        ax.set_xlabel('Frequence (Hz)'); ax.set_ylabel('dB (relatif)')
        ax.set_title('Enceinte %s : woofer, event et somme en champ proche' % cote); ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(out, 'evt_%s_reponses.png' % cote), dpi=130); plt.close(fig)

        if S is not None:
            fig, ax = plt.subplots(figsize=(11, 4))
            ax.semilogx(FGRID, gd, color='#222'); ax.set_xlim(10, 500); ax.set_ylim(0, max(10, np.max(gd[zg]) * 1.2))
            ax.axvline(fb, color='#1f6fb4', ls='--', lw=0.8)
            ax.grid(True, which='both', alpha=0.3); ax.set_xlabel('Frequence (Hz)'); ax.set_ylabel('ms')
            ax.set_title('Enceinte %s : retard de groupe de la somme (en plus du medium 300-600 Hz)' % cote)
            fig.tight_layout(); fig.savefig(os.path.join(out, 'evt_%s_retard.png' % cote), dpi=130); plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.semilogx(FGRID, brut, color='#d9822b', label='event'); ax.semilogx(FGRID, tend, color='#999', ls='--', label='tendance')
        for p in R['resonances_tuyau']:
            ax.annotate('%d Hz\n+%.1f dB' % (p['f_hz'], p['hauteur_db']), (p['f_hz'], np.interp(p['f_hz'], FGRID, brut)),
                        textcoords='offset points', xytext=(0, 8), ha='center', fontsize=8)
        ax.set_xlim(50, 2000); ax.grid(True, which='both', alpha=0.3); ax.legend()
        ax.set_xlabel('Frequence (Hz)'); ax.set_ylabel('dB'); ax.set_title('Enceinte %s : resonances de tuyau de l\'event' % cote)
        fig.tight_layout(); fig.savefig(os.path.join(out, 'evt_%s_tuyau.png' % cote), dpi=130); plt.close(fig)

    R['_courbe'] = (lisser(db(S), 24) if S is not None else lisser(db(W), 24))
    return R

# ---------------------------------------------------------------- principal
def main(argv=None, mes=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('fichiers', nargs='*' if mes is not None else '+', help='.mdat REW ou exports .txt')
    ap.add_argument('--out', default='resultats_event')
    ap.add_argument('--d-membrane', type=float, help='diametre membrane a mi-suspension (mm)')
    ap.add_argument('--d-event', type=float, help='diametre interieur event (mm), ou largeur si rectangulaire')
    ap.add_argument('--d-event2', type=float, help='hauteur (mm) si event rectangulaire')
    ap.add_argument('--l-event', type=float, help='longueur event (mm)')
    ap.add_argument('--n-event', type=int, default=1, help="nombre d'events par caisse")
    ap.add_argument('--vb', type=float, help='volume interieur brut de la caisse (litres)')
    ap.add_argument('--vd-litres', type=float, default=0, help='volume occupe par woofer, renforts, event (litres)')
    ap.add_argument('--rayon-bords', type=float, default=0, help="rayon des bords arrondis de l'event (mm)")
    ap.add_argument('--bords-arrondis', type=int, choices=[0, 1, 2], default=2,
                    help="nombre d'extremites arrondies (avec --rayon-bords)")
    ap.add_argument('--remplissage', choices=list(REMPLISSAGE), default='aucun',
                    help='rembourrage : aucun, parois (parois garnies), partiel, plein')
    ap.add_argument('--dist-mousse', type=float, help="distance rembourrage - entree interieure de l'event (mm)")
    ap.add_argument('--terminaisons', choices=['2bords', '1bord', 'libre'], default='1bord',
                    help="extremites de l'event : 2 bords colles a un panneau, 1 seul, ou aucun")
    ap.add_argument('--phase-minimale', action='store_true', help='ignorer la phase mesuree')
    ap.add_argument('--signe-event', choices=['auto', '+', '-'], default='auto')
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if mes is None:
        mes = charger(a.fichiers)
    print('Mesures trouvees :', ', '.join(sorted(mes)))
    th = theorie(a)
    res = dict(theorie=th, cotes={})
    if a.d_event:
        d_eq = a.d_event / 1000 if not a.d_event2 else 2 * math.sqrt(a.d_event * a.d_event2 * 1e-6 / math.pi)
        r_b = (a.rayon_bords or 0) / 1000 if a.bords_arrondis >= 1 else 0.0
        # le micro est a la sortie exterieure ; l'arrondi est suppose de ce cote s'il y en a un
        res['geometrie'] = {'rayon_gorge_m': d_eq / 2, 'rayon_sortie_m': d_eq / 2 + r_b, 'n_event': a.n_event}
    for cote in 'GD':
        r = analyser_cote(mes, cote, a, a.out)
        if r: res['cotes'][cote] = r
    if not res['cotes']:
        sys.exit("Aucune paire 'woofer X' / 'event X' trouvee. Verifier les noms dans REW.")
    if len(res['cotes']) == 2:
        g, d = res['cotes']['G'], res['cotes']['D']
        res['ecart_fb_GD_hz'] = round(g['fb_creux_woofer_hz'] - d['fb_creux_woofer_hz'], 1)
        cg, cd_ = g['_courbe'], d['_courbe']
        zn, zc = (FGRID > 100) & (FGRID < 200), (FGRID > 30) & (FGRID < 150)
        dif = (cg - np.mean(cg[zn])) - (cd_ - np.mean(cd_[zn]))
        res['ecart_forme_GD_30_150_db'] = round(float(np.max(np.abs(dif[zc]))), 2)
    plt = _plt()
    if len(res['cotes']) == 2 and plt is not None:
        fig, ax = plt.subplots(figsize=(11, 5))
        for c, col in (('G', '#1f6fb4'), ('D', '#c0392b')):
            y = res['cotes'][c]['_courbe']; y = y - np.mean(y[(FGRID > 100) & (FGRID < 200)])
            ax.semilogx(FGRID, y, color=col, label='%s (Fb %.1f Hz)' % (c, res['cotes'][c]['fb_creux_woofer_hz']))
        ax.set_xlim(10, 500); ax.set_ylim(-40, 15); ax.grid(True, which='both', alpha=0.3); ax.legend()
        ax.set_xlabel('Frequence (Hz)'); ax.set_ylabel('dB (cale 100-200 Hz)'); ax.set_title('Gauche contre droite')
        fig.tight_layout(); fig.savefig(os.path.join(a.out, 'evt_comparaison_GD.png'), dpi=130); plt.close(fig)
    for r in res['cotes'].values(): r.pop('_courbe', None)
    json.dump(res, open(os.path.join(a.out, 'resultats.json'), 'w'), indent=2, ensure_ascii=False)

    L = ['# Resultats event bass-reflex', '']
    if th:
        L += ['Theorie : Fb %.1f Hz, longueur totale %d mm (arrondis R%d mm x %d), longueur effective %d mm, '
              'surface %.1f cm2, volume net %.1f l, rembourrage %s (volume apparent %.1f l), '
              'resonances de tuyau prevues %s Hz' % (th['fb_theorique_hz'], th['longueur_totale_mm'],
              th['rayon_bords_mm'], th['bords_arrondis'], th['longueur_effective_mm'],
              th['surface_event_cm2'], th['volume_net_l'], th['remplissage'], th['volume_apparent_l'],
              ', '.join(map(str, th['resonances_tuyau_prevues_hz'])))]
        L += ['- ATTENTION : ' + w for w in th['avertissements']] + ['']
    for c, r in res['cotes'].items():
        L.append('## Enceinte %s' % c)
        for k, v in r.items():
            if k != 'avertissements': L.append('- %s : %s' % (k, v))
        for w in r['avertissements']: L.append('- ATTENTION : ' + w)
        L.append('')
    if 'ecart_fb_GD_hz' in res: L.append('Ecart d\'accord gauche - droite : %.1f Hz' % res['ecart_fb_GD_hz'])
    open(os.path.join(a.out, 'resume.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return res

if __name__ == '__main__':
    main()
