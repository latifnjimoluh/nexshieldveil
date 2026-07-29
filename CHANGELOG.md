# Journal des modifications

Toutes les versions notables de NexShieldVeil (distribution `privacy-guard`).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnage [SemVer](https://semver.org/lang/fr/).

Rappel de périmètre, valable pour toutes les versions : NexShieldVeil **réduit** le
risque de regard indiscret, il ne le supprime pas. Voir [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## [0.3.3] — 2026-07-29

### Ajouté
- Le programme d'installation Windows est habillé aux couleurs du produit : le
  logo apparaît sur la page d'accueil et dans l'en-tête de chaque page du wizard
  (posé sur l'ardoise de la marque), en plus de l'icône déjà présente sur le
  `Setup.exe` et l'application installée.

## [0.3.2] — 2026-07-29

### Ajouté
- Identité visuelle : le logo NexShieldVeil (bouclier à l'œil voilé) est posé
  partout — icône de l'application et de la barre des tâches, icône de la barre
  d'état système (tray), icône du `.exe` et de l'installeur Windows, et lockup
  affiché dans « À propos » et l'onboarding. Repli automatique sur l'ancien
  bouclier dessiné si un asset manque.
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

- **Masquer quand je m'éloigne** (désactivé par défaut) : l'écran se masque après
  un délai sans aucun visage devant la caméra. Il réagit à l'absence, jamais à
  l'identité — n'importe quel visage lève le masque.
- La surveillance se met en pause pendant qu'une session est verrouillée
  (Windows et Linux/logind ; macOS non couvert).
- La cadence de capture s'adapte : elle retombe à 5 fps quand personne n'est là
  depuis 30 s, et repart à plein régime dès qu'un visage apparaît.
- Curseur **Réactivité** : le lissage qui ajoutait une latence cachée au masquage
  est désormais visible et réglable.
- La taille physique de l'écran est lue auprès du système au démarrage, au lieu
  de supposer un 24 pouces.

### Corrigé
- Le voile plein écran affichait ses libellés en français en dur, quelle que soit
  la langue choisie.
- Deux personnes côte à côte à distance comparable faisaient basculer le titre
  d'« utilisateur principal » d'une image à l'autre — et ce titre décide quel
  regard est ignoré, donc chaque bascule inversait la décision.
- Le réglage de lissage n'atteignait pas le pipeline (`tracking` était absent de
  la config transmise au worker).
- La cadence réelle était inférieure à la consigne : la pause était fixe et
  s'ajoutait au temps de traitement au lieu de l'absorber.
- Le selfcheck QML (`nexshieldveil --check`) sortait en succès alors que les
  view-models étaient collectés par le ramasse-miettes et que toutes les liaisons
  échouaient à l'exécution. Il vérifie désormais aussi les erreurs de liaison, et
  tourne en CI.

- Correction manuelle de la géométrie d'écran (largeur, hauteur, position de la
  caméra) quand la mesure système est fausse ou absente.
- Correction du regard par l'iris, **désactivée par défaut** et non validée sur
  matériel.
- Release automatisée sur tag : installeur Windows et `SHA256SUMS` publiés, modèle
  MediaPipe vérifié par empreinte, binaire gelé auto-testé avant publication.
- Dépendances verrouillées (empreintes) pour la CI et le build.
- Job CI non bloquant exerçant les vrais adaptateurs OpenCV/MediaPipe.

### Retiré
- L'ancienne fenêtre Qt Widgets (`nexshieldveil-classic`, `python -m privacy_guard.ui`)
  et son dialogue de mise à jour : tout ce qu'elle détenait encore vit désormais
  dans l'interface QML.

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
