# Historique des courbes avant/apres

Chaque fichier ici capture un changement d'EQ : la courbe mesuree (ou
projetee) avant, et apres, avec les parametres de filtre modifies.

Convention de nommage : `eq_<sujet>_<AAAAMMJJ>.json`

Champs communs a chaque fichier :
- `date`, `description`
- `chart_url` (lien vers le graphique interactif sur claude.ai, si publie)
- `freq_hz`, `before_db`, `after_db` (memes longueurs, alignes par indice)
- `changes` : parametres de filtre modifies (avant -> apres)

Champ optionnel :
- `measured: true/false` par courbe si certains points viennent d'une
  vraie mesure au micro et d'autres d'une projection calculee - sinon
  s'appuyer sur la description du fichier.
