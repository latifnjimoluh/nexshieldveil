# Audit indépendant — NexShieldVeil / `privacy-guard`

> Auditeur : revue externe critique, en lecture seule. Aucune correction appliquée.
> Date : 2026-06-27. Commit audité : `4e5a87e` (branche `main`).
> Méthode : lecture intégrale du code + exécution réelle des outils (pytest+cov, ruff,
> mypy, bandit, pip-audit) + vérifications empiriques ciblées. Sorties brutes dans
> `docs/audit/raw/`.

---

## 1. Résumé exécutif

**Note de risque global : FAIBLE** (pour le périmètre réellement livré : le *cœur de
décision pur*). **Préparation production : NON.**

### La promesse de confidentialité est-elle réellement tenue par le code ? — OUI (vérifié)

La revue statique exhaustive du dossier `src/` ne révèle **aucune** écriture d'image
(`imwrite`/`imsave`/`save`/`tofile`/`pickle`), **aucune** sortie réseau
(`socket`/`requests`/`urllib`/`httpx`/`http`/`download`/télémétrie), et **aucune**
persistance biométrique. La seule I/O fichier est la lecture TOML via `tomllib`
(stdlib, local). La caméra est libérée (`cv2.VideoCapture.release()` dans `close()`),
les `FrameSource` exposent un context manager, et les frames ne sont pas accumulées
(prouvé par test `weakref` + revue). Aucune reconnaissance d'identité : seule de la
géométrie est calculée. `bandit -r src` : **0 problème**. `pip-audit` sur les
dépendances réelles du projet (`numpy`, `pydantic`) : **0 CVE**.

→ **La garantie « traitement local, rien sur disque, rien sur le réseau » tient au
niveau du code.** Nuance importante (cf. PRIV-1) : les *tests* de confidentialité ne
prouvent cela que sur le chemin synthétique, pas sur les vrais adaptateurs.

### Le projet est-il prêt pour la production ? — NON

Le **cœur de décision pur** (`config`, `geometry`, `tracking`, `policy`, `masking`)
est d'excellente qualité : typé strict, testé sincèrement, couverture 98–100 %. Mais
le **produit assemblé** ne l'est pas :

1. Les stratégies de masquage `pixelate`/`blur` **ne sont jamais câblées** dans
   l'application réelle ; l'overlay Qt peint un voile plat et ignore
   `config.masking.strategy` (ARCH-1 / CLAIM-1).
2. **Aucune concurrence** : la boucle capture→inférence tourne sur le thread appelant
   et aucun event loop Qt (`app.exec()`) n'est lancé ; le chemin runtime réel est
   non couvert et non validé (CONC-1) — la DoD du projet le reconnaît d'ailleurs
   explicitement (case non cochée).
3. Dépendances non épinglées, pas de lock, pas de scan supply-chain en CI (DEP-1/CI-1).

C'est un **MVP du cœur logique très soigné**, pas un logiciel fini.

---

## 2. Ce qui est bien fait

- **Honnêteté documentaire exemplaire.** `ROADMAP`, `ARCHITECTURE`, `PRIVACY`,
  `LIMITATIONS` sont cohérents et sans sur-promesse d'invisibilité. `LIMITATIONS.md`
  liste correctement les menaces non couvertes (caméra qui filme, hors-champ, reflets,
  téléobjectif, fenêtre de latence). Le « verrou physique » est expliqué d'emblée.
- **Séparation pur/adaptateurs réelle** via interfaces injectables (`FrameSource`,
  `FaceDetector`, `Renderer`) : tout le flux de décision tourne *headless*.
- **Tests cœur sincères** : `policy` (hystérésis), `geometry` (+ hypothesis),
  `tracking`, `config` testent un vrai comportement, avec assertions fortes et cas
  limites (aucun visage, observateur non regardant, glance bref, etc.). Pas de test
  tautologique sur ces modules.
- **Qualité statique** : `ruff check` + `ruff format --check` propres ;
  `mypy` strict propre sur le cœur **et** sur l'ensemble des 24 fichiers ;
  `bandit` propre ; aucun secret commité ; `.gitignore` exclut `*.task`/`models/`.
- **Périmètre respecté** : aucune reconnaissance d'identité, aucune Approche B/C,
  aucun composant réseau/cloud.

---

## 3. Constats

### 3.1 Confidentialité & sécurité

#### PRIV-1 — Les tests de confidentialité ne couvrent que le chemin synthétique · **Moyenne** · *vérifié*
- **Emplacement** : `tests/privacy/test_privacy.py:28-52` (`_run_session`) ; `docs/PRIVACY.md:12-21`.
- **Description** : tous les tests privacy exécutent `SyntheticFrameSource` +
  `ScriptedFaceDetector` + `RecordingRenderer` — c.-à-d. des doublures en numpy/Python
  pur. Or les **seuls** composants susceptibles d'ouvrir un socket ou d'écrire un
  fichier sont les *vrais* adaptateurs (`MediaPipeFaceDetector`, `WebcamFrameSource`,
  `QtOverlayRenderer`), jamais exercés ici (non installés en CI). Le test
  « aucun réseau » garde donc du code qui n'avait de toute façon aucune raison
  d'ouvrir une connexion.
- **Impact** : `PRIVACY.md` affirme « enforced by automated tests » ; en réalité la
  garantie tient par revue statique, pas par les tests sur le vrai chemin. Une
  régression introduisant un `cv2.imwrite` ou un appel réseau dans un adaptateur ne
  serait **pas** détectée par la CI.
- **Preuve** : `tests/privacy/test_privacy.py:30-36` instancie uniquement les doublures.
  `pytest -m privacy -v` → 5 passed (`docs/audit/raw/pytest-privacy.txt`). Recherche
  `imwrite|requests|socket|urllib` dans `src/` → **aucune** occurrence
  (`docs/audit/raw/` ; cf. grep §Résumé). La garantie est donc vraie *par le code*,
  pas *par les tests*.
- **Recommandation** : ajouter un test qui, lorsque MediaPipe/OpenCV/Qt **sont**
  présents (job CI optionnel avec `[vision,ui]`), rejoue une courte session réelle
  sous le même garde réseau/fichier. À défaut, ajouter un test statique (AST/grep) qui
  échoue si un symbole interdit (`cv2.imwrite`, `socket`, `requests`, …) apparaît dans
  `src/`. Reformuler `PRIVACY.md` pour distinguer « garanti par revue » de
  « gardé par test ».

#### PRIV-2 — `test_no_files_written_during_run` ne patche que `builtins.open` · **Faible** · *vérifié*
- **Emplacement** : `tests/privacy/test_privacy.py:55-74`.
- **Description** : l'espion ne couvre que `builtins.open`. Une écriture via `os.open`,
  `os.write`, `pathlib.Path.write_bytes`, ou un writer C (p. ex. `cv2.imwrite`,
  cache modèle MediaPipe) **contournerait** la détection. `numpy.save/savez` sont
  séparément interdits, ce qui est bien, mais la couverture reste partielle.
- **Impact** : faux sentiment de complétude du garde « aucune écriture disque ».
- **Preuve** : `monkeypatch.setattr(builtins, "open", spy_open)` (ligne 64) est le seul
  point d'interception d'écriture générique.
- **Recommandation** : compléter avec un garde au niveau OS (p. ex. patcher `os.open`)
  ou s'appuyer sur `test_no_image_files_appear_on_disk` étendu aux vrais adaptateurs.

#### DEP-1 — Dépendances non épinglées, aucun lockfile · **Moyenne** · *vérifié*
- **Emplacement** : `pyproject.toml:17-40`.
- **Description** : toutes les dépendances utilisent des bornes ouvertes (`numpy>=1.26`,
  `pydantic>=2.6`, `mediapipe>=0.10.9`, `PySide6>=6.6`, …) sans fichier de verrouillage
  (`requirements.txt`/`constraints`/`uv.lock`). L'installation n'est pas reproductible :
  deux installations à deux dates donnent des arbres de dépendances différents.
- **Impact** : non-reproductibilité ; exposition non maîtrisée aux nouvelles versions
  (régressions, CVE introduites en amont). Contredit l'exigence « dépendances
  épinglées/verrouillées, installation reproductible ».
- **Preuve** : `pyproject.toml` lignes 17-40 ; aucun lockfile dans `git ls-files`.
- **Recommandation** : générer et committer un lock (`uv lock` / `pip-compile`) pour
  l'environnement CI, ou borner les majeures (`numpy>=1.26,<3`).

#### DEP-2 — `pip-audit` exécuté sur l'interpréteur global ; absent de la CI · **Info** · *vérifié*
- **Description** : l'exécution `pip-audit` a tourné sur le Python global (pas de venv
  isolé), d'où une majorité de CVE provenant de paquets **étrangers au projet**
  (`pillow`, `scrapy`, `torch`, `twisted`, `starlette`, `requests`…). Les dépendances
  *directes* du projet (`numpy 2.4.0`, `pydantic 2.12.5`) ne présentent **aucune** CVE.
- **Impact** : aucun (constat de méthode) ; mais la CI ne lance ni `pip-audit` ni
  `bandit` (cf. CI-1) → la chaîne d'appro n'est pas surveillée automatiquement.
- **Preuve** : `docs/audit/raw/pip-audit.txt` ; `.github/workflows/ci.yml:36-55`.
- **Recommandation** : exécuter `pip-audit`/`bandit` dans un venv isolé en CI.

### 3.2 Intégrité & qualité des tests

#### TEST-1 — Le module `masking` est testé en isolation mais jamais utilisé par l'app · **Moyenne** · *vérifié*
- **Emplacement** : `tests/unit/test_masking.py` (122 assertions sur les stratégies) ;
  intégration absente.
- **Description** : `make_mask_strategy`, `VeilMask`, `PixelateMask`, `BlurMask` sont
  couverts à 99 % par des tests unitaires, donnant l'impression que « le masquage
  fonctionne ». Mais aucun test (ni aucun code applicatif) ne vérifie qu'ils sont
  réellement appliqués au rendu (cf. ARCH-1). La couverture verte masque une
  fonctionnalité non intégrée.
- **Impact** : confiance trompeuse ; deux des trois stratégies annoncées sont
  inertes en production sans qu'aucun test ne le signale.
- **Preuve** : `grep make_mask_strategy|MaskStrategy|\.apply\(` → occurrences
  uniquement dans `masking/` et `tests/`, **jamais** dans `app.py` ni `overlay/`.
- **Recommandation** : câbler le masquage (cf. ARCH-1) puis ajouter un test
  d'intégration vérifiant que la stratégie configurée est effectivement appliquée.

### 3.3 Architecture & exactitude fonctionnelle

#### ARCH-1 — Les stratégies `pixelate`/`blur` ne sont jamais câblées au runtime · **Moyenne** · *vérifié*
- **Emplacement** : `src/privacy_guard/app.py:196-203` ;
  `src/privacy_guard/overlay/qt_overlay.py:52-81`.
- **Description** : `build_runtime_components` crée
  `QtOverlayRenderer(opacity=config.masking.opacity)` et n'utilise jamais
  `make_mask_strategy`. `QtOverlayRenderer` peint un rectangle de couleur unie et
  ignore `config.masking.strategy`, `blur_radius`, `pixelate_blocks`. Choisir
  `strategy = "pixelate"` ou `"blur"` dans la config **n'a aucun effet**. De plus
  `mss` (capture d'écran nécessaire au flou/pixelisation d'un contenu réel) est
  déclaré mais **jamais importé** : il n'existe aucune capture d'écran à flouter.
- **Impact** : fonctionnalité annoncée partiellement inopérante. La confidentialité
  *de base* n'est pas compromise (le voile plat masque bien), mais la promesse
  « veils / pixelates / blurs » du README est fausse pour 2 modes sur 3.
- **Preuve** : `qt_overlay.py:55` n'accepte que `opacity` ; `app.py:198`
  n'instancie le renderer qu'avec `opacity`. Aucun import de `masking` dans `app.py`
  / `overlay/`. `grep mss` → seulement `pyproject.toml:30` et `:102`, jamais dans `src/`.
- **Recommandation** : soit câbler une vraie capture (`mss`) + `MaskStrategy` dans un
  renderer, soit restreindre honnêtement le périmètre (config + README) au seul voile,
  comme le fait déjà la note honnête du ROADMAP M7.

#### CONC-1 — Aucune concurrence ; pas d'event loop Qt ; chemin runtime non validé · **Moyenne** · *vérifié*
- **Emplacement** : `src/privacy_guard/app.py:140-148` (`run`), `:220-235` (`main`) ;
  `src/privacy_guard/overlay/qt_overlay.py:71-81`.
- **Description** : `PrivacyGuardPipeline.run()` est une boucle **synchrone** sur le
  thread appelant. Dans le câblage réel, `QtOverlayRenderer` crée une `QApplication`
  mais **`app.exec()` n'est jamais appelé** ; les évènements Qt ne sont pompés
  (`processEvents`) que dans `set_masked()`, et seulement lors d'une *transition*
  (retour anticipé si l'état ne change pas). `WebcamFrameSource.read()` (bloquant)
  s'exécute sur ce même thread. L'exigence « capture/inférence hors du thread UI » est
  **non remplie** ; il n'existe ni `QThread`, ni `threading`, ni `asyncio`.
- **Impact** : en exécution réelle, l'overlay risque de ne pas se repeindre / de ne pas
  rester réactif entre deux transitions ; pas de séparation capture/UI. Robustesse
  insuffisante pour la production.
- **Preuve** : `grep QThread|threading|asyncio|app\.exec|\.start\(\)` dans `src/` →
  **aucune** occurrence (seulement `Kalman1D`). Tout le câblage runtime est
  `# pragma: no cover` (`app.py:159, 220, 229-234`), confirmé par la couverture
  (`app.py` 86 %, lignes 208-235 manquantes). La DoD du projet
  (`docs/ROADMAP.md:38`) laisse d'ailleurs la validation machine réelle **non cochée**.
- **Recommandation** : déporter capture+inférence dans un `QThread`/worker, lancer
  `app.exec()`, protéger l'état partagé, et ajouter un smoke-test du chemin réel.

#### FUNC-1 — Double lissage : la latence effective de masquage dépasse `trigger_ms` · **Faible** · *vérifié empiriquement*
- **Emplacement** : `src/privacy_guard/app.py:118-122`.
- **Description** : un EMA (`smoothing_alpha=0.4`, seuil `>= 0.5`) est appliqué au
  signal binaire « observateur présent » **avant** la machine à hystérésis. Quand un
  observateur apparaît après des frames « clear », l'EMA met ~1 frame à franchir 0.5,
  qui s'ajoute à `trigger_ms`. La latence réelle = `trigger_ms` + échauffement EMA.
- **Impact** : la latence de masquage excède la valeur configurée (~12,5 % ici) ; le
  contenu reste visible un peu plus longtemps que ce que `trigger_ms` laisse croire.
  Comportement non documenté. (LIMITATIONS #3 mentionne la fenêtre de latence mais pas
  le surcoût EMA.)
- **Preuve** : mesure reproductible — observateur apparu à la frame 10 (=500 ms),
  masquage à la frame 19 (=950 ms) avec `trigger_ms=400` → ~450 ms réels
  (`docs/audit/raw/` ; sortie du script de vérification dans la conversation d'audit).
- **Recommandation** : documenter la latence effective, ou rendre l'EMA optionnel sur
  ce signal binaire (la machine `policy` fournit déjà l'anti-clignotement), ou exposer
  `alpha`/seuil dans la config.

#### ARCH-2 — `Kalman1D` implémenté et testé mais inutilisé · **Faible** · *vérifié*
- **Emplacement** : `src/privacy_guard/tracking/filters.py:64-105`.
- **Description** : le filtre de Kalman 1D n'est référencé nulle part hors de son
  `__init__.py` et de ses tests ; l'app utilise `ExponentialSmoother`. Code mort de
  fait (présenté comme « optionnel » dans ROADMAP H2).
- **Impact** : surface de maintenance inutile ; acceptable mais à clarifier.
- **Preuve** : `grep Kalman1D src/` → seulement définition + ré-export.
- **Recommandation** : soit l'exposer via la config (choix EMA/Kalman), soit le retirer.

#### ARCH-3 — Dépendance `mss` déclarée mais jamais importée · **Faible** · *vérifié*
- **Emplacement** : `pyproject.toml:30`.
- **Description** : `mss>=9.0` figure dans l'extra `ui` mais n'est importé nulle part
  dans `src/`. Vestige de la fonctionnalité de capture/flou jamais construite (cf.
  ARCH-1).
- **Preuve** : `grep mss` → uniquement `pyproject.toml`, jamais dans `src/`.
- **Recommandation** : retirer la dépendance tant que la capture n'est pas implémentée.

#### FUNC-2 — Repli `screen.center()` quand le rayon ne coupe pas le plan · **Info** · *vérifié*
- **Emplacement** : `src/privacy_guard/geometry/gaze.py:126-137`.
- **Description** : si le rayon de regard est parallèle au plan ou pointe en arrière
  (`hit is None`), la cible se replie sur le centre de l'écran. Pour un regard
  franchement opposé (`+z`), l'angle reste grand → correctement « non regardant »
  (testé). Le cas parallèle exact est un cas-limite étroit, sans impact pratique vu la
  tolérance angulaire généreuse.
- **Preuve** : couverture `gaze.py:136` (branche « face exactement sur la cible »)
  non atteinte — cas dégénéré bénin.
- **Recommandation** : aucune action requise ; éventuellement traiter `hit is None`
  comme « non regardant » plutôt que repli centre, par prudence.

### 3.4 Qualité de code & hygiène dépôt / CI

#### CI-1 — CI sans scan de vulnérabilités ni bandit ; chemin adaptateur jamais compilé · **Moyenne** · *vérifié*
- **Emplacement** : `.github/workflows/ci.yml:31-55`.
- **Description** : la CI lance lint + format + mypy + tests + privacy + perf (bon),
  mais **pas** `pip-audit` ni `bandit`. Elle n'installe que `[dev]` (sans
  `vision,ui`), donc `mediapipe_detector`/`opencv_sources`/`qt_overlay` ne sont jamais
  importés en CI (par conception, mais cela laisse le chemin runtime non vérifié).
- **Impact** : surveillance supply-chain absente ; régression de sécurité possible non
  détectée.
- **Preuve** : `ci.yml` ne contient aucune étape `pip-audit`/`bandit`.
- **Recommandation** : ajouter des étapes `bandit -r src` et `pip-audit` (venv isolé) ;
  envisager un job optionnel `[vision,ui]` pour un smoke-test réel.

#### HYG-1 — Motif `omit` de couverture obsolète (ne matche aucun fichier) · **Faible** · *vérifié*
- **Emplacement** : `pyproject.toml:126`.
- **Description** : `omit = ["*/overlay/*", "*/capture/webcam*"]`. Le second motif ne
  correspond à aucun fichier : la source webcam s'appelle `opencv_sources.py`. L'omit
  visé est donc inopérant, d'où `opencv_sources.py` à 50 % de couverture (trompeur).
- **Preuve** : rapport de couverture `docs/audit/raw/pytest-cov.txt`
  (`opencv_sources.py … 50%`).
- **Recommandation** : corriger en `*/capture/opencv_sources*` (ou retirer l'omit et
  assumer la couverture réelle des gardes d'import).

#### HYG-2 — Incohérence de nommage produit (`NexShieldVeil`) vs paquet (`privacy_guard`) · **Faible** · *vérifié*
- **Emplacement** : dépôt `nexshieldveil` vs `pyproject.toml:6` (`name = "privacy-guard"`)
  et tout le code/doc en `privacy_guard`/« Privacy Guard ».
- **Impact** : confusion potentielle (probable renommage produit non répercuté).
- **Recommandation** : aligner le nom du paquet/produit, ou documenter l'alias.

### 3.5 Audit des affirmations

#### CLAIM-1 — README sur-promet « veils / pixelates / blurs » · **Faible** · *vérifié*
- **Emplacement** : `README.md:4-6`.
- **Description** : « automatically masks (veils / pixelates / blurs) the content ».
  Seul le voile est câblé (cf. ARCH-1).
- **Recommandation** : restreindre la formulation au voile, ou câbler les autres modes.

#### CLAIM-2 — `PRIVACY.md` « enforced by automated tests » sur-affirme · **Faible** · *vérifié*
- **Emplacement** : `docs/PRIVACY.md:9-31`.
- **Description** : les tests n'appliquent ces gardes qu'au chemin synthétique
  (cf. PRIV-1). La garantie tient par revue de code, pas par les tests sur le vrai
  chemin.
- **Recommandation** : nuancer la formulation et/ou renforcer les tests.

---

## 4. Tableau récapitulatif

| Sévérité | Nombre | Identifiants |
|---|---|---|
| Critique | 0 | — |
| Élevée | 0 | — |
| Moyenne | 5 | PRIV-1, TEST-1, ARCH-1, CONC-1, CI-1, DEP-1 *(6)* |
| Faible | 7 | PRIV-2, FUNC-1, ARCH-2, ARCH-3, HYG-1, HYG-2, CLAIM-1, CLAIM-2 *(8)* |
| Info | 2 | DEP-2, FUNC-2 |

> Correctif de comptage : **6 moyennes** (PRIV-1, TEST-1, ARCH-1, CONC-1, CI-1, DEP-1),
> **8 faibles** (PRIV-2, FUNC-1, ARCH-2, ARCH-3, HYG-1, HYG-2, CLAIM-1, CLAIM-2),
> **2 info** (DEP-2, FUNC-2). Aucune critique, aucune élevée.

---

## 5. Couverture & qualité des tests par module

Exécution : `pytest --cov` → **121 passed, 1 skipped** (OpenCV absent),
couverture totale **94 %** (`docs/audit/raw/pytest-cov.txt`).

| Module | Type | Couv. | Jugement qualitatif |
|---|---|---|---|
| `config/models.py` | cœur | 100 % | Excellent — défauts, bornes, clés inconnues, invariant release≥trigger, round-trip. |
| `config/loader.py` | cœur | 100 % | Bon — fichier manquant, overrides, validation. |
| `geometry/gaze.py` | cœur | 98 % | Excellent — unitaire + hypothesis (unité, symétrie, monotonie, intersection). 1 branche dégénérée non couverte (FUNC-2). |
| `geometry/types.py` | cœur | 100 % | Bon. |
| `tracking/filters.py` | cœur | 98 % | Bon — convergence, réduction de variance, anti-aliasing vecteurs. Kalman testé mais inutilisé (ARCH-2). |
| `policy/state_machine.py` | cœur | 100 % | Excellent — hystérésis, déclenchement, levée, glance bref, reset, trigger=0. Le plus solide. |
| `masking/strategies.py` | cœur | 99 % | Bon en isolation **mais non intégré** (TEST-1/ARCH-1). |
| `app.py` | wiring | 86 % | Boucle pure bien testée (intégration/E2E) ; câblage runtime non couvert (CONC-1). |
| `capture/frame_source.py` | adapt. | 100 % | Bon — synthétique, déterminisme, context manager, non-accumulation. |
| `capture/opencv_sources.py` | adapt. | 50 % | Faible — seul le garde d'import est testé ; `read/close/timestamp` non couverts (besoin matériel). Omit obsolète (HYG-1). |
| `vision/detector.py` | adapt. | 100 % | Bon — détecteur scripté, listes indépendantes. |
| `vision/mediapipe_detector.py` | adapt. | 88 % | Acceptable — chemin lourd `pragma: no cover` (assumé), garde de dégradation testé. |
| `vision/observation.py` | adapt. | 100 % | Bon. |
| `overlay/*` | adapt. | omis | `RecordingRenderer` testé ; `QtOverlayRenderer` exclu (pas d'affichage en CI) — assumé. |

**Sincérité globale** : les six niveaux demandés (unit, component, integration,
system/E2E, performance, privacy) existent et sont exécutés. Les tests du **cœur**
sont sincères et non tautologiques. Les réserves portent sur (a) la portée limitée des
tests de confidentialité (PRIV-1/PRIV-2), (b) l'absence de test d'intégration du
masquage (TEST-1), et (c) le chemin runtime/concurrence non couvert (CONC-1).

---

## 6. Verdict

- **Confidentialité (code)** : **tenue** — aucune fuite disque/réseau, aucune
  persistance biométrique, aucune identification, caméra libérée. Risque résiduel :
  les *tests* ne le prouvent que sur le chemin synthétique (PRIV-1).
- **Risque global** : **FAIBLE** sur le périmètre livré.
- **Production** : **NON prêt** — masquage non câblé (pixelate/blur), aucune
  concurrence/UI loop, dépendances non verrouillées, supply-chain non surveillée en CI.
  Recommandation : traiter les 6 constats « Moyenne » avant tout usage réel
  (cf. `docs/audit/REMEDIATION.md`).
