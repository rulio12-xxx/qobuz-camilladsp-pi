# Archive des fichiers de la Pi absents de git (copie du 22/11/2026)

Copie en lecture seule depuis la Pi (`~/camilladsp/configs/`), rien n'a ete
modifie la-bas. Ces fichiers ne sont pas utilises par CamillaDSP : ils servent
d'historique. Les configs actives et les FIR de la Pi etaient identiques au depot.

- `sauvegardes-configs/` : les 73 sauvegardes `*.avant-*` (et `camilladsp.yml.bak`)
  faites automatiquement avant chaque ecriture dans les YAML. Le suffixe dit ce
  qui a ete change ensuite :
  - `avant-lampes` (30/08), `avant-kick` (22/09), `avant-gain` (vinyle, 08/11) ;
  - 18/11 : `avant-kick`, `avant-renfort` (clic), `avant-fir`, `avant-preamp`, `avant-aigu` ;
  - 20/11 : `avant-retour` (= reglage du 18/11 complet, FIR compris), `avant-pente`.
  Les `*.avant-tube.avant-*` sont les memes etapes sur les fichiers sans lampes.
- `backup-juillet-2026/` : `~/camilladsp/configs/backup/` (juillet 2026, debut du projet) :
  - `camilladspClaude.yml` (= `camilladspRAW.yml`) : premiere correction faite a la main,
    avant REW : headroom -6 dB, passe-haut Butterworth 28 Hz ordre 4, **renfort
    Lowshelf 100 Hz +5 dB Q0,7**, modes G 55 / 93 / 160 Hz, D 151 / 215 Hz.
  - `*.20260726-093720` et `*.115604` : etats du 26/07 (REW5 avec retards G/D ajoutes).
  - `test.yml` : config vide de test du loopback.
  - `camilladspREW1..5.yml` ne sont pas recopies ici : identiques a `camilladsp/rew-history/`.
- `configs-kick-anciennes/` : `camilladsp-{qobuz,fichiers,bluetooth}-kick.yml`, anciennes
  copies (= config actuelle sans la pente d'aigu ni les lampes) ; aucun script du depot ne
  les utilise.

`.gitignore` ignore `*.avant-*` : pour ajouter de nouvelles sauvegardes ici,
`git add -f correction/archive-pi/...`.

Mesures REW brutes (76 fichiers `.mdat`, 19 et 26/07/2026, 74 Mo compresses) : trop
lourdes pour git, gardees hors depot (fichiers du projet Claude :
`correction/rew-mesures-2026-07.tgz`, copie de `C:\Users\heipp\REW\temp` sur le PC).
