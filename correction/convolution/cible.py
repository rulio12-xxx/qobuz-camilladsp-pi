"""Courbe cible du grave (22/11/2026) : forme de la reponse D avec l'EQ REW3 de juillet.
0 dB = niveau moyen 200-500 Hz. Meme cible pour G et D."""
import numpy as np
from filtres import rbj, butter_hp


def cible_db(f, bosse=11.0, fbosse=58.0):
    db = lambda h: 20 * np.log10(np.abs(h) + 1e-12)
    c = db(rbj({"type": "Peaking", "freq": fbosse, "gain": bosse, "q": 0.8}, f)) \
        + db(rbj({"type": "Lowshelf", "freq": 110, "gain": 4.0, "q": 0.6}, f)) \
        + db(butter_hp(32, 4, f))
    return c - np.mean(c[(f >= 200) & (f <= 500)])
