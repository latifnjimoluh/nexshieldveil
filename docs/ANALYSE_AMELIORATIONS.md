# Analyse & propositions d'amélioration — NexShieldVeil v0.3.1

> Revue de code complète du dépôt à `63363f8` (branche `main`), après les chantiers
> M-FP1..7 (flou/pixelisation live) et M-R1..3 (fiabilité). Objectif : identifier ce
> qui reste entre l'état actuel et un produit qu'on peut mettre entre les mains
> d'utilisateurs, puis proposer des actions concrètes et priorisées.
>
> Chaque constat porte une référence `fichier:ligne` vérifiable et une action chiffrée
> (S ≤ 1 h · M ≈ ½ j · L ≈ 1–2 j).

---

## 0. Statut — vague 1 livrée

| ID | Statut | Livré |
|---|---|---|
| **AM-1** | ✅ | `ui/autostart.py` : plan pur par OS (registre Windows, `.desktop` XDG, LaunchAgent macOS) + adaptateurs ; le shell applique et **réconcilie avec l'état réel** au démarrage ; la case est grisée là où aucun mécanisme n'existe, et revient à la vérité si l'écriture est refusée. |
| **AM-2** | ✅ | Clés `overlay.title`/`overlay.subtitle`, libellés transmis à la fabrique d'overlay, reconstruction sur changement de langue. |
| **AM-3** | ✅ | `UpdatesViewModel` + `UpdateView.qml` + entrée tray + vérification différée de 30 s (opt-out), entièrement traduits. |
| **AM-4** | ✅ | URL contrainte aux hôtes GitHub (redirections comprises), SHA-256 publié vérifié avant lancement, répertoire de téléchargement privé. |
| **AM-12** | ✅ | `DownscaledFrameSource` branché avant la détection, avec preuve expérimentale que la pose de tête est invariante par changement d'échelle. |
| **AM-16** | ✅ | Selfcheck QML réparé (il passait au vert avec **toutes** les liaisons cassées) puis ajouté à la CI ; liste de vues unique. |
| **AM-20** | ✅ | Étude déplacée dans `docs/`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, templates d'issue. |

## 0 bis. Statut — vague 2 livrée

| ID | Statut | Livré |
|---|---|---|
| **AM-8** | ✅ | `PrimaryUserSelector` : le sortant garde le titre sauf si un challenger le dépasse d'une marge pendant N images ; suivi **par position**, pas par indice de liste. Test d'intégration avec contre-épreuve. |
| **AM-7** | ✅ | Troisième seuil dans la machine à états (`absence_ms`, désactivé par défaut) + raison du masquage remontée jusqu'à l'interface, avec sa propre formulation. |
| **AM-11** | ✅ | `tracking` manquait dans `app_config_from_snapshot` — le réglage n'atteignait jamais le worker. Ajouté, plus un curseur « Réactivité » qui dit ce qu'on échange. |
| **AM-13** | ✅ | `AdaptiveCadence` : régulation par échéance (la pause absorbe le traitement au lieu de s'y ajouter) + repli à 5 fps après 30 s d'image vide, plein régime dès qu'un visage apparaît ou que le masque est posé. |
| **AM-10** | ✅ | Taille d'écran lue via `QScreen.physicalSize()` derrière un filtre de plausibilité pur (EDID est souvent faux) ; une taille écrite dans le TOML l'emporte. Asymétrie multi-écran documentée. |
| **AM-14** | ✅ | `SessionSuspender` (pur) + adaptateurs Windows et logind. **macOS non implémenté**, dit explicitement plutôt qu'approximé. |

## 0 ter. Statut — vague 3 livrée

| ID | Statut | Livré |
|---|---|---|
| **AM-5** | ✅ | `requirements-ci.txt` universel, épinglé et vérifié par empreinte, utilisé par la CI ; bornes ouvertes conservées pour les installations utilisateur. |
| **AM-6** | ✅ | `release.yml` sur tag : environnement verrouillé, modèle MediaPipe vérifié par empreinte épinglée, selfcheck **du binaire gelé**, Inno Setup, `SHA256SUMS` publiés (ce dont dépend AM-4). Deux garde-fous sur la version. |
| **AM-17** | ✅ | Job non bloquant `[vision,ui]` + tests de session réelle sur clip généré. A révélé au passage que `ci.yml` ne parsait plus depuis la vague 1 : les workflows ont maintenant leurs tests. |
| **AM-18** | ✅ | `control_window.py`, le point d'entrée `classic` et le dialogue mort supprimés ; la spec PyInstaller corrigée (elle ignorait tous les modules importés paresseusement depuis). |
| **AM-9** | ✅ (désactivé) | Géométrie iris pure et testée, extraction derrière `detection.use_iris`. **Non validé sur matériel** — un mauvais décalage déplace le rayon de regard. |
| **AM-10b** | ⚠️ partiel | Correction manuelle de la géométrie livrée. L'assistant guidé « quatre coins » **n'est pas fait** : sans matériel, impossible de vérifier que la tolérance déduite est saine. |
| **AM-19** | ⚠️ partiel | Le README dit enfin quelle plateforme est packagée et ce qui diffère ailleurs. Le packaging macOS/Linux lui-même reste à faire. |

Reste ouvert : l'assistant de calibration guidé, le packaging macOS/Linux, et
toute la validation matérielle (§8). Le reste de ce document est l'analyse
d'origine, conservée telle quelle comme référence.

---

## 1. Résumé exécutif

**L'état de santé technique est bon.** Ce qui a été construit est solide : la
séparation logique pure / adaptateurs tient, le cœur de décision est typé strict et
testé sincèrement, la garantie de confidentialité est mécaniquement gardée (AST sur
tout `src/`), et les six constats « Moyenne » de l'audit externe ont bien été traités
(masquage réellement câblé, concurrence via `QThread`, CI durcie, garde statique).

Vérifications relancées pour cette analyse (Python 3.11.15, `[dev,ui]` installés) :

| Contrôle | Résultat |
|---|---|
| `pytest -m "not slow and not requires_hardware"` (avec PySide6) | **420 passed, 2 skipped** |
| Couverture totale | **96 %** (cœur : 98–100 %) |
| `ruff check .` / `ruff format --check .` | propre / 110 fichiers formatés |
| Parité i18n `fr.json` ↔ `en.json` | 103 clés des deux côtés, aucun écart |

**Le problème n'est donc plus la qualité du code : c'est l'écart résiduel entre ce que
l'interface promet et ce que le produit fait réellement**, plus une série de leviers
non exploités sur la qualité de détection, l'autonomie et la distribution.

Trois constats de niveau **P0** (promesse fausse, visible par l'utilisateur) :

1. **`Démarrer à la session` ne démarre rien** — le réglage est affiché, coché,
   persisté… et aucun code ne l'enregistre auprès de l'OS.
2. **Le voile plein écran est en français en dur** — un utilisateur EN lit
   « Contenu masqué » sur la surface la plus visible de l'application.
3. **L'application QML (celle que l'installeur livre) ne vérifie jamais les mises à
   jour** — seule l'ancienne fenêtre `classic` câble l'updater.

---

## 2. Constats P0 — l'interface promet ce que le code ne fait pas

### AM-1 · « Démarrer à la session » est un interrupteur inerte · **Élevée** · vérifié

- **Emplacements** : `src/privacy_guard/ui/views/SettingsView.qml:218-221` et
  `OnboardingView.qml:128-131` (les deux cases à cocher) →
  `ui/viewmodels/settings.py:172-174` → `ui/controller.py:275-277` →
  `ui/state.py:113` (`start_at_login: bool`) → `ui/persistence.py` (persisté dans
  `QSettings`).
- **Description** : la valeur voyage jusqu'au store et revient au redémarrage, mais
  **rien n'écrit jamais dans un mécanisme de démarrage de session** :
  `grep -rn "winreg\|LaunchAgent\|\.desktop\|autostart\|HKEY\|plist" src/ packaging/`
  ne renvoie **aucune** occurrence. `packaging/installer.iss` n'a pas non plus de
  section `[Registry]`. La docstring de `controller.py:276` dit pourtant
  « the shell persists/**applies** it » — le shell ne fait que persister.
- **Impact** : l'utilisateur coche la case, redémarre sa machine, et se croit protégé
  alors que l'app n'a jamais démarré. C'est la pire classe de bug pour un logiciel de
  sécurité : une protection absente que l'interface affirme active. C'est aussi
  frontalement contraire à la règle d'honnêteté du projet.
- **Proposition** :
  1. Un module pur `ui/autostart.py` qui **calcule** l'action (chemin de l'exécutable,
     clé/fichier cible, contenu à écrire) sans effet de bord — donc testable headless
     sur les trois OS, comme `persistence.py` l'est déjà ;
  2. trois adaptateurs minces : `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
     (Windows), `~/.config/autostart/nexshieldveil.desktop` (Linux/XDG),
     `~/Library/LaunchAgents/` (macOS) ;
  3. le shell applique à chaque `config_changed`, et **relit l'état réel** au démarrage
     pour que la case reflète l'OS, pas le souhait ;
  4. option repli honnête si l'écriture échoue (session gérée, droits) : la case se
     décoche avec un message, jamais un silence.
- **Note** : l'écriture d'un fichier `.desktop` / d'une clé de registre passera devant
  la garde AST (`open(..., "w")` est interdit). C'est **volontaire et sain** : il faut
  ajouter une entrée d'allow-list explicite et argumentée dans
  `tests/privacy/test_source_hygiene.py`, comme cela a été fait pour l'updater —
  et un test prouvant que ce module ne peut importer aucun code caméra/vision.
- **Effort** : M (+ S pour la garde AST).

### AM-2 · Le voile affiche du français en dur, quelle que soit la langue · **Élevée** · vérifié

- **Emplacements** : `src/privacy_guard/overlay/qt_overlay.py:60-61`
  (`_DEFAULT_TITLE = "Contenu masqué"`, `_DEFAULT_SUBTITLE = "Un observateur regarde
  votre écran"`), utilisés par défaut en `:238-239` et `:357-358`.
  `build_qt_masking_renderer` (`qt_overlay.py:317-343`) n'expose aucun paramètre de
  libellé, et `ui/core_controller.py:279-281` le construit sans jamais toucher au
  `Translator`.
- **Impact** : toute l'application est traduite FR/EN (103 clés, parité parfaite) —
  sauf l'écran qui recouvre la totalité du moniteur au moment le plus critique. Un
  utilisateur anglophone voit du français plein écran sans savoir pourquoi son écran
  vient d'être masqué.
- **Proposition** : ajouter `overlay.title` / `overlay.subtitle` aux catalogues i18n,
  passer les libellés traduits à `build_qt_masking_renderer`, et reconstruire (ou
  re-libeller) l'overlay sur `translator.language_changed` — le shell fait déjà
  exactement ce schéma pour le menu tray (`shell.py:225-236`, `relabel()`).
  Ajouter un test de vue vérifiant qu'aucune chaîne visible n'est en dur dans
  `overlay/`.
- **Effort** : S.

### AM-3 · L'app QML ne vérifie jamais les mises à jour · **Moyenne** · vérifié

- **Emplacements** : `ui/shell.py:124` n'importe de `updater_ui` que `shield_icon` ;
  le seul appel à `auto_check_enabled()` / `UpdateCheckThread` est dans l'UI héritée
  (`ui/control_window.py:79-123`). `packaging/app_entry.py` fait pointer l'exécutable
  gelé sur `ui.shell:main`.
- **Impact** : l'installeur Windows livre l'interface QML → **aucun utilisateur
  installé ne sera jamais informé d'une mise à jour**, y compris pour un correctif de
  sécurité. Tout le module `update/` (quarantiné, testé, documenté dans `PRIVACY.md`)
  est de fait mort dans le produit distribué.
- **Proposition** : recâbler l'updater dans le shell QML — vérification différée
  (~30 s après le démarrage, pour ne pas retarder la protection), résultat exposé par
  un view-model dédié, entrée « Mises à jour » dans le menu tray, et la case
  opt-out déjà existante (`_AUTO_CHECK_KEY`) remontée dans les Réglages QML.
- **Effort** : M.

---

## 3. Sécurité de la chaîne de distribution

### AM-4 · L'installeur téléchargé est exécuté sans aucune vérification d'intégrité · **Moyenne** · vérifié

- **Emplacements** : `src/privacy_guard/update/checker.py:87-104`
  (`download_installer`) puis `:107-112` (`launch_installer` → `subprocess.Popen`).
  Destination : un répertoire `tempfile` (`ui/updater_ui.py`).
- **Description** : rien ne vérifie que le binaire téléchargé est bien celui publié —
  ni empreinte SHA-256, ni signature Authenticode. `installer_url` est pris tel quel
  dans la réponse de l'API, sans contrôle du domaine hôte. Et entre l'écriture dans un
  répertoire temporaire et le lancement, rien ne garantit que le fichier n'a pas été
  remplacé (fenêtre TOCTOU sur un `/tmp` partagé).
- **Impact** : le seul chemin réseau du produit est aussi celui qui **exécute du code**
  sur la machine de l'utilisateur. TLS couvre le transport, pas l'authenticité de
  l'artefact ni sa protection après écriture. C'est le risque résiduel le plus élevé du
  dépôt aujourd'hui — modéré en probabilité, maximal en impact.
- **Proposition** (les trois, par ordre de rapport valeur/effort) :
  1. **Empreinte publiée** : joindre `SHA256SUMS` à chaque release, la vérifier avant
     tout lancement, échouer bruyamment sinon ;
  2. **Domaine hôte contraint** : n'accepter `installer_url` que sur
     `github.com` / `objects.githubusercontent.com`, redirections comprises ;
  3. **Répertoire privé** : télécharger dans un dossier créé en `0700` propre à
     l'utilisateur, pas dans le `tempfile` par défaut ; à terme, **signer** l'exécutable
     (certificat de signature de code) et vérifier la signature avant exécution.
- **Effort** : S (1+2) / M (3, hors coût du certificat).

### AM-5 · Toujours pas de verrouillage de dépendances reproductible · **Faible** · vérifié

- **Emplacement** : `pyproject.toml:17-40`.
- **Description** : DEP-1 est marqué « Fait » dans `docs/audit/REMEDIATION.md`, mais
  uniquement via des **bornes de majeures** (`numpy>=1.26,<3`). Deux installations à
  deux dates continuent de produire des arbres différents ; la CI et le build de
  l'installeur ne sont pas reproductibles.
- **Proposition** : committer un `requirements-ci.txt` généré (`pip-compile
  --generate-hashes` ou `uv lock`) utilisé **uniquement** par la CI et le build
  PyInstaller, en gardant les bornes ouvertes pour les installations utilisateur.
  Renouvellement mensuel automatisable (Dependabot / Renovate).
- **Effort** : S.

### AM-6 · Le build de l'installeur est entièrement manuel · **Faible** · vérifié

- **Emplacements** : `packaging/build.ps1`, `packaging/installer.iss` ;
  `.github/workflows/` ne contient que `ci.yml`.
- **Description** : produire une release demande une machine Windows, une exécution
  manuelle de PyInstaller puis d'Inno Setup. Aucun artefact n'est reproductible ni
  tracé, et rien ne relie une release à un commit.
- **Proposition** : un workflow `release.yml` déclenché sur tag — build PyInstaller,
  exécution du **selfcheck** (`nexshieldveil --check`, déjà écrit en
  `ui/shell.py:39-87` et jamais lancé en CI), compilation Inno Setup, génération des
  empreintes, publication de la release. C'est aussi ce qui alimente AM-4.1.
- **Effort** : M.

---

## 4. Qualité de la détection — les leviers non exploités

Ce sont les propositions qui améliorent la **protection elle-même**, pas son emballage.

### AM-7 · Un inconnu seul devant l'écran n'est jamais détecté · **Moyenne** · vérifié

- **Emplacements** : `src/privacy_guard/app.py:126-134` — `observer_present` est
  `any(hit for i, hit in enumerate(looking) if i != primary_index)`, et
  `geometry/gaze.py:140-176` élit toujours un visage principal dès qu'il y en a un.
- **Description** : conséquence logique de la règle « le visage le plus central/proche
  est l'utilisateur » — s'il n'y a qu'un visage, c'est *forcément* l'utilisateur. Donc
  le scénario « je m'absente, quelqu'un s'installe devant mon écran » ne déclenche
  **jamais** de masquage. C'est aussi le scénario de fuite le plus banal en open space.
- **Description honnête de la contrainte** : sans reconnaissance d'identité — exclue du
  périmètre, à raison — on ne *peut pas* savoir que ce visage n'est pas le vôtre. Le
  levier disponible n'est donc pas « reconnaître l'intrus » mais « réagir à l'absence ».
- **Proposition** : un **verrouillage d'absence** optionnel (désactivé par défaut) :
  si aucun visage n'est détecté pendant `absence_ms` (défaut suggéré ~10 s), masquer,
  et ne lever qu'au retour d'un visage. Toute la logique tient dans la machine à états
  `policy` (pure, 100 % couverte) avec un troisième seuil ; l'UI l'expose comme
  « Masquer quand je m'éloigne ». À documenter dans `LIMITATIONS.md` : cela ne
  distingue toujours pas *qui* revient.
- **Effort** : M.

### AM-8 · L'élection de l'utilisateur principal n'a aucune stabilité temporelle · **Moyenne** · vérifié

- **Emplacement** : `geometry/gaze.py:140-176`, appelé à chaque image depuis
  `app.py:128-132`.
- **Description** : le score `centralité + taille` est recalculé image par image sans
  mémoire. Deux personnes assises côte à côte à distance comparable produisent des
  scores proches, et un micro-mouvement suffit à faire basculer le titre de « principal »
  d'un visage à l'autre. Or ce titre décide **qui est ignoré** : à chaque bascule, la
  détection s'inverse. Le lissage EMA de `tracking` porte sur le booléen final, il ne
  corrige pas une inversion d'identité — et l'hystérésis de `policy` ne fait que
  retarder l'oscillation.
- **Impact** : faux positifs et faux négatifs alternés dans le cas d'usage le plus
  probable (deux personnes devant un écran) — celui-là même que le produit vise.
- **Proposition** : une hystérésis d'élection dans `tracking` (module pur, donc
  testable sans matériel) : le principal sortant garde le titre tant qu'un challenger
  ne le dépasse pas d'une marge `epsilon` pendant `N` images consécutives. ~30 lignes,
  entièrement propriétés-testables (`hypothesis` est déjà utilisé sur `geometry`).
- **Effort** : M.

### AM-9 · Le regard est estimé à la pose de tête seule, les iris sont ignorés · **Faible** · vérifié

- **Emplacements** : `vision/mediapipe_detector.py:43-56` (6 points de modèle,
  `_LANDMARK_IDS = (1, 152, 33, 263, 61, 291)`), `:147-172` (`solvePnP`).
  `grep -rni "iris" src/` → aucune occurrence.
- **Description** : le Face Landmarker de MediaPipe fournit les repères d'iris ; le
  projet n'utilise que six points de contour pour un `solvePnP`. Conséquence : un
  observateur qui garde la tête droite et **déplace seulement les yeux** vers l'écran
  est classé « ne regarde pas » (faux négatif), et l'utilisateur qui tourne la tête en
  gardant les yeux sur son écran est mal caractérisé.
- **Proposition** : dériver un décalage yaw/pitch de la position de l'iris dans
  l'orbite et le composer avec la pose de tête, derrière un drapeau de configuration
  (`detection.use_iris`, défaut `false` tant que ce n'est pas validé sur machine
  réelle), avec dégradation propre si les repères manquent. La composition elle-même
  est de la géométrie pure → testable headless. **À valider impérativement sur
  matériel avant activation par défaut** : c'est le genre de changement qui peut
  dégrader autant qu'améliorer.
- **Effort** : L.

### AM-10 · La géométrie d'écran est saisie à la main et suppose un seul moniteur · **Faible** · vérifié

- **Emplacements** : `config/models.py:57-70` (`screen_width_mm=520`,
  `screen_height_mm=290`, `camera_above_screen_mm=10`) ; `geometry/types.py:20-45`
  (`ScreenModel`, plan `z=0` unique). `grep -rn "physicalSize" src/` → rien.
- **Description** : les défauts correspondent à un 24" 16:9. Sur un 13" portable
  (~290×170 mm), le rectangle modélisé est presque **quatre fois trop grand**, donc le
  test « ce regard tombe-t-il sur l'écran ? » est bien plus permissif que prévu — la
  sensibilité réelle ne correspond pas au réglage affiché. Personne ne mesurera son
  écran au réglet. Par ailleurs l'overlay est multi-écran depuis M-FP4
  (`qt_overlay.py:259-274`) alors que la géométrie de décision reste mono-plan.
- **Proposition** : (a) auto-renseigner largeur/hauteur via
  `QScreen.physicalSize()` au premier démarrage, avec possibilité de correction
  manuelle ; (b) mini-assistant de calibration dans l'onboarding (« regardez les quatre
  coins ») qui ajuste `gaze_tolerance_deg` sur des mesures réelles plutôt qu'un défaut
  générique ; (c) documenter explicitement dans `LIMITATIONS.md` que la décision
  raisonne sur l'écran principal — le masquage, lui, couvre bien tous les écrans.
- **Effort** : S (a) / L (b) / S (c).

### AM-11 · L'EMA sur un signal binaire reste non réglable depuis l'interface · **Faible** · vérifié

- **Emplacements** : `app.py:145-150` ; `config/models.py:73-81`.
- **Description** : FUNC-1 de l'audit a été traité **par la documentation**
  (`LIMITATIONS.md` §3) : la latence effective vaut `trigger_ms` + échauffement EMA.
  Mais `tracking.smoothing_alpha` n'est ni exposé dans les Réglages, ni persisté, ni
  transmis par `app_config_from_snapshot` (`ui/core_controller.py:62-81` recompose
  `camera`, `geometry`, `policy`, `masking` — **pas** `tracking`). Un utilisateur qui
  trouve le masquage trop lent n'a aucun moyen d'agir dessus depuis l'app.
- **Proposition** : soit exposer `smoothing_alpha` (option avancée), soit — plus lisible
  — remplacer l'EMA sur ce booléen par un compteur « K images regardantes sur N », qui
  exprime la même robustesse au bruit dans une unité que l'utilisateur comprend, et
  supprime la latence cachée. Dans les deux cas, ajouter `tracking` à
  `app_config_from_snapshot`.
- **Effort** : S.

---

## 5. Performance, autonomie, matériel

### AM-12 · `camera.downscale_width` est documenté mais n'est appliqué nulle part · **Moyenne** · vérifié

- **Emplacements** : déclaré en `config/models.py:29-34`, annoncé en
  `config.example.toml:9` (« frames downscaled to this width before vision (speed) »).
  `grep -rn "downscale_width" src/` → **une seule occurrence, la déclaration**.
- **Impact** : l'inférence MediaPipe tourne sur les images à la résolution native de la
  webcam (souvent 1280×720, parfois 1920×1080) alors que la détection de visage n'a
  besoin que de ~640 px de large. C'est le poste de consommation CPU dominant d'une app
  censée tourner en permanence en tâche de fond — et le réglage censé le corriger ne
  fait rien. Accessoirement : encore une clé de configuration morte.
- **Proposition** : appliquer le redimensionnement dans `WebcamFrameSource` (ou dans un
  décorateur `DownscaledFrameSource` pur, dans l'esprit de `ResilientFrameSource`),
  **avant** `detector.detect`. Attention : la position 3D issue de `solvePnP`
  (`mediapipe_detector.py:147-172`) dépend de la focale déduite de la largeur d'image —
  le facteur d'échelle doit être propagé, sinon la géométrie se décale. À couvrir par
  un test de non-régression comparant les angles à deux résolutions.
- **Effort** : M.

### AM-13 · La cadence n'est pas régulée et ne s'adapte à rien · **Faible** · vérifié

- **Emplacement** : `ui/core_controller.py:178` —
  `self.msleep(int(1000 / max(1, self._config.camera.target_fps)))`.
- **Description** : la pause est **fixe** et s'ajoute au temps de traitement, donc la
  cadence réelle est toujours inférieure à la consigne (à 15 fps demandés et 25 ms
  d'inférence, on obtient ~11 fps — et la latence de masquage dérive d'autant). Et la
  charge est **constante** : même cadence quand personne n'est là depuis une heure que
  lorsqu'un observateur est détecté.
- **Proposition** : (a) régulation par échéance (dormir `période − temps écoulé`), et
  (b) cadence adaptative — par exemple ~5 fps quand aucun visage n'a été vu depuis 30 s,
  la cadence nominale dès qu'un visage apparaît, et la cadence pleine tant que le
  masquage est engagé. Sur un portable, c'est la différence entre une app qu'on garde et
  une app qu'on désinstalle parce qu'elle vide la batterie. Le compromis (une seconde
  personne peut apparaître pendant une phase lente) doit être écrit noir sur blanc dans
  `LIMITATIONS.md`.
- **Effort** : M.

### AM-14 · Rien ne suspend la caméra quand la session est verrouillée · **Faible**

- **Description** : `M-R1` gère la reprise après veille, mais aucun code ne réagit au
  **verrouillage de session** ou à l'extinction de l'écran : la webcam continue de
  produire des images à analyser alors qu'il n'y a plus rien à protéger. Coût en CPU,
  en batterie — et en perception (le voyant caméra reste allumé écran verrouillé, ce qui
  inquiète légitimement un utilisateur soucieux de vie privée).
- **Proposition** : s'abonner aux signaux de session (`WM_WTSSESSION_CHANGE` sous
  Windows, `org.freedesktop.login1` sous Linux, notifications de distributed center sous
  macOS) et suspendre le worker — le mécanisme de pause/reprise existe déjà et est testé
  (M-R3). Adaptateur par OS, logique de décision pure et testable.
- **Effort** : M.

### AM-15 · Ouverture de la webcam non optimisée sous Windows · **Faible** · vérifié

- **Emplacement** : `capture/opencv_sources.py:38` — `cv2.VideoCapture(target)`, sans
  indication de backend ni de résolution.
- **Description** : sous Windows, le backend par défaut (MSMF) est connu pour mettre
  plusieurs secondes à ouvrir un périphérique là où `CAP_DSHOW` répond quasi
  immédiatement. Ce délai est payé au démarrage **et à chaque reconnexion** M-R1 (donc à
  chaque sortie de veille). Aucune résolution n'est demandée non plus, ce qui laisse le
  pilote choisir (souvent le maximum — cf. AM-12).
- **Proposition** : passer `cv2.CAP_DSHOW` sur `sys.platform == "win32"`, fixer
  `CAP_PROP_FRAME_WIDTH/HEIGHT` selon `downscale_width`, et mesurer le temps
  d'ouverture avant/après (à faire sur machine réelle : non vérifiable en CI).
- **Effort** : S.

---

## 6. Tests, CI et dette

### AM-16 · Le selfcheck QML existe mais n'est jamais exécuté en CI · **Faible** · vérifié

- **Emplacements** : `ui/shell.py:39-87` (`_selfcheck`, exposé par `--check`) ;
  `.github/workflows/ci.yml` ne l'appelle pas.
- **Détail** : la liste `_VIEWS` (`shell.py:24-36`) est **dupliquée** dans
  `tests/ui/test_views.py:17-29` (`ALL_VIEWS`). Une vue ajoutée à l'une et pas à l'autre
  passe inaperçue.
- **Proposition** : exporter une liste unique de vues consommée par les deux, et ajouter
  une étape CI `nexshieldveil --check` — c'est le seul test qui valide le **câblage
  assemblé** (moteur QML + contexte + view-models), et il est déjà écrit.
- **Effort** : S.

### AM-17 · Le chemin réel (`[vision]`) n'est jamais exercé automatiquement · **Faible**

- **Description** : la CI installe `[dev,ui]` mais jamais `[vision]` : `MediaPipe` et
  `opencv-python` ne sont importés dans aucun job. Une régression dans
  `mediapipe_detector.py` ou `opencv_sources.py` (couverture 89 % / non couverte) ne
  serait détectée que par un test manuel sur machine.
- **Proposition** : un job **non bloquant** `[vision,ui]` qui rejoue une courte session
  sur un clip vidéo (via `VideoFileFrameSource`, déjà écrit) avec un vrai modèle
  MediaPipe mis en cache, sous les gardes réseau/fichier des tests `-m privacy`. Cela
  couvre à la fois la recommandation PRIV-1 de l'audit et la validation du chemin réel.
  Le clip doit être synthétique et sans visage réel identifiable, pour ne pas committer
  de données biométriques dans le dépôt.
- **Effort** : L.

### AM-18 · Deux interfaces en parallèle · **Faible** · vérifié

- **Description** : `ui/control_window.py` (448 lignes, Qt Widgets) coexiste avec le
  shell QML. Le README annonce sa disparition (« le temps de la bascule ») mais elle
  détient encore la seule fonctionnalité de mise à jour (AM-3) et l'aperçu caméra
  historique. C'est de la dette qui grossit : chaque évolution doit être pensée deux
  fois, ou n'être faite que d'un côté (ce qui est déjà le cas).
- **Proposition** : décider et écrire la date de suppression. Prérequis : AM-3
  (l'updater passe côté QML). Ensuite retirer `control_window.py`, le point d'entrée
  `nexshieldveil-classic`, et les entrées `omit` de couverture associées
  (`pyproject.toml`).
- **Effort** : M (après AM-3).

### AM-19 · Distribution Windows uniquement · **Faible** · vérifié

- **Description** : la CI teste Ubuntu/Windows/macOS, mais `packaging/` ne produit qu'un
  `.exe` + un installeur Inno Setup. Un utilisateur macOS ou Linux doit cloner le dépôt
  et gérer un venv — ce n'est pas un produit grand public. À noter aussi :
  `QScreen.grabWindow(0)` (`overlay/qt_grabber.py:47-77`) ne fonctionne pas sous Wayland
  sans portail ; le repli voile est prévu (P4) et documenté, mais l'expérience Linux
  serait dégradée sans que l'utilisateur en soit prévenu à l'installation.
- **Proposition** : à défaut de packager les trois OS tout de suite, **dire lequel est
  supporté** dans le README (aujourd'hui il ne le dit pas), et prioriser un `.dmg`
  macOS ou un AppImage selon la demande réelle.
- **Effort** : L par plateforme.

### AM-20 · Hygiène de dépôt · **Info** · vérifié

- `etude-confidentialite-ecran.md` (14 ko) traîne à la racine alors que tout le reste
  de la documentation est dans `docs/`.
- Pas de `CHANGELOG.md` : l'historique des versions n'existe que dans les messages de
  commit `build(release):` — et l'updater affiche les notes de release GitHub, qui ne
  sont alimentées par rien d'automatique.
- `.github/` ne contient que `workflows/ci.yml` : ni templates d'issue, ni
  `CONTRIBUTING.md`, ni `SECURITY.md` (utile pour un produit de confidentialité : où
  signaler une faille ?).
- **Effort** : S pour l'ensemble.

---

## 7. Plan proposé

### Vague 1 — « ne plus promettre ce qu'on ne fait pas » (≈ 3–4 j)

| # | Constat | Pourquoi en premier |
|---|---|---|
| 1 | **AM-1** autostart réel | Une protection annoncée et absente ; le pire défaut possible ici. |
| 2 | **AM-2** i18n du voile | S, très visible, corrige une incohérence de qualité flagrante. |
| 3 | **AM-4.1/4.2** empreinte + domaine de l'installeur | Seul chemin qui exécute du code téléchargé. |
| 4 | **AM-3** updater dans le shell QML | Sans lui, aucun correctif ne parviendra aux utilisateurs installés. |
| 5 | **AM-12** appliquer `downscale_width` | Config morte + poste CPU dominant. |
| 6 | **AM-16, AM-20** selfcheck en CI, hygiène | Quick wins. |

### Vague 2 — « mieux protéger » (≈ 5–7 j)

| # | Constat | Gain |
|---|---|---|
| 7 | **AM-8** stabilité de l'utilisateur principal | Supprime une oscillation dans le cas d'usage principal. |
| 8 | **AM-7** verrouillage d'absence | Couvre le scénario de fuite le plus banal. |
| 9 | **AM-13, AM-14** cadence adaptative, pause en session verrouillée | Autonomie = rétention. |
| 10 | **AM-10a/c** géométrie auto + doc | Aligne la sensibilité réelle sur la sensibilité affichée. |
| 11 | **AM-11** latence réglable ou compteur K/N | Rend l'arbitrage compréhensible. |

### Vague 3 — « industrialiser & approfondir » (≈ 8–12 j)

| # | Constat |
|---|---|
| 12 | **AM-6, AM-5** release automatisée + verrouillage des dépendances |
| 13 | **AM-17** job CI `[vision,ui]` sur clip vidéo |
| 14 | **AM-18** suppression de l'UI classic |
| 15 | **AM-9** regard iris (validation matérielle obligatoire) |
| 16 | **AM-10b** assistant de calibration ; **AM-19** packaging multiplateforme |

---

## 8. Ce qui n'a pas pu être vérifié ici

Cette analyse est statique et headless : ni webcam, ni écran, ni modèle MediaPipe dans
l'environnement de revue. N'ont donc **pas** été mesurés — et ne doivent pas être
considérés comme validés :

- la latence réelle de masquage bout en bout sur matériel ;
- la qualité de détection (taux de faux positifs / faux négatifs) en conditions réelles ;
- le comportement de l'overlay multi-écran, du click-through et de la capture
  freeze-frame sur un vrai bureau (et sous Wayland) ;
- le temps d'ouverture de la webcam par backend (AM-15) ;
- l'effet réel des propositions AM-9 (iris) et AM-13 (cadence adaptative), qui peuvent
  dégrader la détection autant que l'améliorer selon les conditions.

La case « reste à valider sur une vraie machine » de `docs/ROADMAP.md:38` reste donc
pertinente, et devrait le rester tant qu'une campagne de test matériel documentée n'aura
pas été menée.

---

## 9. Table de correspondance

| ID | Sévérité | Effort | Fichier principal |
|---|---|---|---|
| AM-1 autostart inerte | Élevée | M | `ui/controller.py:275`, `ui/persistence.py` |
| AM-2 voile non traduit | Élevée | S | `overlay/qt_overlay.py:60-61` |
| AM-3 updater absent du shell QML | Moyenne | M | `ui/shell.py:124` |
| AM-4 installeur non vérifié | Moyenne | S/M | `update/checker.py:87-112` |
| AM-5 pas de lockfile | Faible | S | `pyproject.toml` |
| AM-6 release manuelle | Faible | M | `packaging/`, `.github/workflows/` |
| AM-7 inconnu seul non détecté | Moyenne | M | `app.py:126-134`, `policy/` |
| AM-8 principal instable | Moyenne | M | `geometry/gaze.py:140-176` |
| AM-9 iris inutilisés | Faible | L | `vision/mediapipe_detector.py:43-56` |
| AM-10 géométrie manuelle/mono-écran | Faible | S–L | `config/models.py:57-70` |
| AM-11 EMA non réglable | Faible | S | `app.py:145-150` |
| AM-12 `downscale_width` inutilisé | Moyenne | M | `config/models.py:29-34` |
| AM-13 cadence non régulée | Faible | M | `ui/core_controller.py:178` |
| AM-14 pas de pause en session verrouillée | Faible | M | `ui/core_controller.py` |
| AM-15 backend webcam Windows | Faible | S | `capture/opencv_sources.py:38` |
| AM-16 selfcheck hors CI + liste dupliquée | Faible | S | `ui/shell.py:24-36` |
| AM-17 chemin `[vision]` non testé | Faible | L | `.github/workflows/ci.yml` |
| AM-18 deux UI en parallèle | Faible | M | `ui/control_window.py` |
| AM-19 packaging Windows seul | Faible | L | `packaging/` |
| AM-20 hygiène de dépôt | Info | S | racine, `.github/` |
