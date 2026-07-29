# Journal des modifications

Toutes les versions notables de NexShieldVeil (distribution `privacy-guard`).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnage [SemVer](https://semver.org/lang/fr/).

Rappel de périmètre, valable pour toutes les versions : NexShieldVeil **réduit** le
risque de regard indiscret, il ne le supprime pas. Voir [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## [Non publié]

### Ajouté
- « Démarrer à la session » est désormais réellement appliqué au système
  (registre Windows, fichier `.desktop` XDG, LaunchAgent macOS). Le réglage était
  jusqu'ici affiché et persisté sans jamais rien enregistrer.
- Vérification des mises à jour dans l'application QML : contrôle différé au
  démarrage (désactivable), entrée « Mises à jour » dans le menu de la barre d'état.
  Seule l'ancienne fenêtre `classic` la proposait.
- Vérification d'intégrité de l'installeur téléchargé : URL contrainte aux domaines
  GitHub (redirections comprises) et empreinte SHA-256 publiée vérifiée avant tout
  lancement. Sans empreinte publiée, l'installation automatique est refusée.
- Le redimensionnement de capture (`camera.downscale_width`) est appliqué avant la
  détection ; la clé de configuration était documentée mais inopérante.
- `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md` et templates d'issue.

### Corrigé
- Le voile plein écran affichait ses libellés en français en dur, quelle que soit
  la langue choisie.
- Le selfcheck QML (`nexshieldveil --check`) sortait en succès alors que les
  view-models étaient collectés par le ramasse-miettes et que toutes les liaisons
  échouaient à l'exécution. Il vérifie désormais aussi les erreurs de liaison, et
  tourne en CI.

### Documentation
- `docs/ANALYSE_AMELIORATIONS.md` : revue complète de la v0.3.1 et propositions
  priorisées.
- L'étude de confidentialité d'écran rejoint `docs/`.

## [0.3.1] — 2026-07

Chantier fiabilité, issu des retours d'un bêta-testeur.

- **M-R1** — Résilience caméra : après une veille ou un débranchement, la boucle de
  surveillance mourait au premier échec de lecture et l'application tournait sans
  plus rien protéger. `ResilientFrameSource` ferme/rouvre la caméra en backoff
  plafonné, en renumérotant frames et timestamps, et la perte est visible.
- **M-R2** — Les réglages survivent au redémarrage et atteignent le pipeline en
  cours de session (ils n'étaient écrits nulle part, et sensibilité/délais ne
  parvenaient pas au worker).
- **M-R3** — Pause temporisée 5/15 min depuis la barre d'état, avec reprise
  automatique.

## [0.3.0] — 2026-07

- **M-FP1 → M-FP7** — Flou et pixelisation réellement appliqués en direct, par
  capture d'écran locale *freeze-frame* : capture, voile immédiat, transformation
  hors thread, puis échange. Multi-moniteur, avec repli sur le voile opaque si la
  capture échoue. Aucune image n'est écrite sur le disque.

## [0.2.1] — 2026-06

- Aperçu caméra opt-in et fenêtre principale.

## [0.2.0] — 2026-06

- Interface QML/Qt Quick (MVVM) en barre d'état système, embarquée dans le bundle
  gelé Windows.

## [0.1.0] — 2026-06

- MVP : cœur de décision complet (`config`, `geometry`, `tracking`, `policy`,
  `masking`), adaptateurs dégradables (webcam, MediaPipe, overlay Qt), pipeline
  assemblé, suite de tests à six niveaux et documentation d'honnêteté
  (`ROADMAP`, `ARCHITECTURE`, `PRIVACY`, `LIMITATIONS`).
- Audit externe indépendant puis remédiation (voir `docs/audit/`).
