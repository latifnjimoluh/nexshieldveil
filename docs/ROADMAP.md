# Privacy Guard — Roadmap

> Logiciel de bureau de **confidentialité d'écran anti-regard indiscret** (« privacy guard »).
> Approche A : détection d'observateur par webcam + masquage automatique du contenu.

Ce document est **rédigé et commité avant toute ligne de code**, conformément aux consignes,
puis **tenu à jour** (cases cochées) au fil de l'avancement.

---

## 0. Verrou physique fondamental (cadre honnête, non négociable)

Sur un écran standard (LCD/OLED), **le logiciel ne contrôle que la valeur de chaque pixel,
jamais la direction d'émission des photons**. On ne peut donc pas « cacher l'écran de côté »
en jouant sur les pixels. Le seul levier réellement logiciel est :

1. **détecter** un observateur via la caméra frontale, puis
2. **masquer/floute** le contenu tant qu'il regarde.

Le produit **réduit fortement le risque** ; il ne **garantit pas** l'invisibilité.
Toute la documentation et tous les commentaires doivent rester honnêtes là-dessus.

---

## 1. Objectif & définition de « terminé » (Definition of Done)

Un MVP est « terminé » lorsque :

- [x] `docs/ROADMAP.md` commité en premier, puis tenu à jour.
- [x] Tous les modules cœur implémentés, typés (`mypy` propre sur le cœur), avec docstrings.
- [x] Suite de tests complète (unit → component → integration → system → performance → privacy) verte.
- [x] Couverture ≥ 85 % sur `geometry`, `tracking`, `policy`, `config`, `masking` (98–100 % atteint).
- [x] `ruff` (lint+format) et `pre-commit` propres ; CI GitHub Actions configurée.
- [x] Tests de confidentialité passent : **aucun réseau sortant**, **aucune frame persistée**.
- [x] Un test d'intégration **déterministe** prouve le déclenchement du masquage **sans matériel**.
- [x] `README`, `ARCHITECTURE`, `PRIVACY`, `LIMITATIONS` complets et honnêtes.
- [x] L'app démarre proprement (et se dégrade proprement sans caméra / sans MediaPipe).
- [ ] *Reste à valider sur une vraie machine avec webcam + modèle MediaPipe (hors CI).*

---

## 2. Périmètre

**DANS le périmètre :**
- Détection d'un visage observateur dont le regard pointe vers l'écran (webcam).
- Distinction utilisateur principal (visage le plus central/proche) vs autres visages.
- Logique de décision à hystérésis (anti-clignotement) pilotant une couche de masquage.
- Overlay transparent, toujours au premier plan, click-through, floutant/obscurcissant.
- Configuration utilisateur (sensibilité, délais, zones, activation caméra) via TOML.

**HORS périmètre (évolutions futures seulement) :**
- Approche B — rendu fovéal contingent au regard.
- Approche C — modulation psychovisuelle temporelle / lunettes synchronisées.
- Toute reconnaissance d'identité des tiers (on détecte « un regard », jamais « qui »).
- Flou GPU temps réel de contenu arbitraire (MVP : flou de capture mss ou voile pixelisé).

---

## 3. Architecture (séparation logique pure / adaptateurs matériels)

```
privacy-guard/
  src/privacy_guard/
    capture/   FrameSource : webcam | fichier | synthétique
    vision/    détection visages + repères + iris (wrapper MediaPipe, dégradable)
    geometry/  pose de tête, vecteur de regard, intersection plan-écran (PUR)
    tracking/  filtre de lissage (exponentiel / Kalman simplifié) (PUR)
    policy/    machine à états + hystérésis (PUR, sans dépendance matérielle)
    masking/   stratégies de masquage (interface + impléms)
    overlay/   fenêtre Qt transparente click-through (adaptateur UI)
    config/    schéma + chargement TOML
    app.py     orchestration du pipeline
  tests/  unit/ component/ integration/ system/ performance/ privacy/
  fixtures/    frames synthétiques + clips courts
  docs/   ROADMAP ARCHITECTURE LIMITATIONS PRIVACY
```

**Cœur testable sans matériel** : `config`, `geometry`, `tracking`, `policy`, `masking`.
**Adaptateurs** (couverture moindre tolérée) : `capture`, `vision`, `overlay`.

Machine à états `policy` : `CLEAR → OBSERVER_DETECTED → MASKED → CLEAR`
avec temporisation (déclenchement après N ms de regard détecté, levée après M ms d'absence).

---

## 4. Jalons & tâches

### M0 — Cadrage (ce document)
- [x] Rédiger et commiter `docs/ROADMAP.md` seul.

### M1 — Scaffolding & qualité
- [x] `pyproject.toml` (deps, ruff, mypy, pytest, coverage, markers).
- [x] Squelette des paquets `src/privacy_guard/*` + `tests/*`.
- [x] `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.gitignore`.

### M2 — `config` (TDD)
- [x] Schéma dataclass/pydantic + chargement/validation TOML + valeurs par défaut.
- [x] Tests : chargement, défauts, validation des bornes, fichier manquant.

### M3 — `geometry` (TDD, fonctions pures + hypothesis)
- [x] Estimation du vecteur de regard à partir de la pose de tête.
- [x] Test « ce regard pointe-t-il vers le plan-écran ? » (intersection).
- [x] Distinction utilisateur principal (centralité/taille).
- [x] Tests propriétés : invariances, bornes, symétries.

### M4 — `tracking` (TDD)
- [x] Filtre de lissage exponentiel (et/ou Kalman simplifié) sur positions/angles.
- [x] Tests : convergence, réduction du bruit, bornes.

### M5 — `policy` (TDD, machine à états pure)
- [x] États + transitions + compteurs de temporisation + hystérésis.
- [x] Tests : déclenchement après seuil, levée après délai, pas avant (hystérésis),
      pas de faux positif avec utilisateur seul.

### M6 — `capture` + `vision` (adaptateurs dégradables)
- [x] `FrameSource` (interface) + `SyntheticFrameSource`, `VideoFileFrameSource`, `WebcamFrameSource`.
- [x] Wrapper MediaPipe `FaceLandmarker` avec dégradation propre si indispo.
- [x] Tests composant : frames synthétiques → repères factices ; absence MediaPipe gérée.

### M7 — `masking`
- [x] Interface `MaskStrategy` + impléms (voile opaque, pixelisation, flou box numpy pur).
      *Note honnête : le flou est un box-blur numpy sur l'image, pas une capture mss GPU
      (notée en évolution future). Le voile/pixelisation couvrent le MVP.*
      *Évolution livrée (v0.3.0) : le flou/pixelisation sont branchés en live via la
      capture d'écran locale freeze-frame — chantier tracé et coché dans
      `docs/ROADMAP_FLOU_PIXELISATION.md`.*
- [x] Tests via interface de rendu mockée (sans fenêtre réelle).

### M8 — `overlay` (adaptateur UI Qt)
- [x] Fenêtre PySide6 transparente, toujours au-dessus, click-through.
- [x] Logique non-matérielle testée ; rendu réel testé manuellement.

### M9 — `app` (orchestration)
- [x] Boucle pipeline : capture → vision → geometry → tracking → policy → masking/overlay.
- [x] Hooks observables pour tests E2E headless.
- [x] Dégradation propre (pas de caméra / pas de MediaPipe / pas d'affichage).

### M10 — Suite de tests complète & fixtures
- [x] Intégration déterministe (SyntheticFrameSource + ScriptedFaceDetector).
- [x] Système/E2E headless via le pipeline assemblé observé par le hook `Renderer`.
      *Note honnête : `VideoFileFrameSource` (OpenCV) est testé en composant et
      sauté si OpenCV absent ; l'E2E déterministe utilise la source synthétique
      pour rester reproductible et sans binaire image sur disque.*
- [x] Performance (FPS, latence < 200 ms cible) marqués `slow`/`performance`.
- [x] Confidentialité : pas de réseau, pas de persistance image, pas d'accumulation de buffers.

### M11 — Documentation & récapitulatif
- [x] `README` (install + exécution), `ARCHITECTURE`, `PRIVACY`, `LIMITATIONS`.
- [x] Récapitulatif final : capacités réelles, limites, prérequis évolutions B/C.

### Chantier fiabilité v0.3.1 (retours bêta-testeur)
- [x] **M-R1 — Résilience caméra.** Après une mise en veille ou un débranchement, la
      boucle de surveillance mourait sur le premier échec de lecture et l'app tournait
      sans plus rien protéger. `ResilientFrameSource` (`capture/resilience.py`, logique
      pure 100 % testée) tolère les ratés transitoires puis ferme/rouvre la caméra en
      backoff plafonné, sans fin, en renumérotant frames et timestamps (MediaPipe exige
      des timestamps strictement croissants). La perte est visible (état « reconnexion
      automatique » + action « Réessayer maintenant »), jamais silencieuse.
- [x] **M-R2 — Persistance des réglages.** Les réglages ne survivaient pas à un
      redémarrage (rien ne les écrivait nulle part) et, plus grave, sensibilité et
      délais ne parvenaient même pas au pipeline en cours de session (le worker
      lisait la config TOML de démarrage). Corrigé : `ui/persistence.py` (logique
      pure : sauvegarde/restauration tolérante via le canal `QSettings` déjà
      utilisé pour langue/onboarding — valeurs stringifiées coercées, junk rejeté,
      bornes clampées par les setters), le worker est construit depuis la config
      fusionnée du snapshot (`app_config_from_snapshot`), et les seuils de
      détection redémarrent le worker avec debounce. Bonus corrigé : flou et
      pixelisation n'émettaient jamais `config_changed`.
- [x] **M-R3 — Pause temporisée.** Deux entrées tray « Pause pendant 5/15 min » :
      la surveillance se coupe (caméra relâchée, comme une pause) puis reprend
      toute seule — pour les moments en famille où une pause permanente finirait
      oubliée. Reprendre/Pause manuels annulent le minuteur ; re-snoozer réarme ;
      l'état affiché distingue honnêtement « pause temporaire (reprise auto) »
      de « pause jusqu'à nouvel ordre ». Jamais persisté (état de session).

### Chantier honnêteté — vague 1 de `docs/ANALYSE_AMELIORATIONS.md`

Revue complète de la v0.3.1. Le code était sain (420 tests verts, 96 % de
couverture) ; l'écart restant portait sur des fonctionnalités **annoncées mais non
câblées** — exactement ce que la règle d'honnêteté du projet interdit.

- [x] **AM-1 — Démarrer à la session.** Le réglage était un interrupteur inerte :
      persisté, jamais enregistré auprès de l'OS. `ui/autostart.py` calcule un plan
      pur par plateforme (registre Windows, `.desktop` XDG, LaunchAgent macOS) et
      l'applique ; l'état affiché est lu du système, une écriture refusée remet
      l'interrupteur à la vérité, et la case est grisée là où aucun mécanisme
      n'existe. Garde AST **renforcée** (violations typées réseau/écriture,
      `write_text`/`write_bytes`/`os.open` désormais attrapés) plutôt qu'assouplie.
- [x] **AM-2 — Libellés du voile.** Le masque plein écran affichait du français en
      dur quelle que soit la langue. Libellés traduits, transmis à la fabrique
      d'overlay, reconstruits au changement de langue.
- [x] **AM-3 — Mises à jour dans l'app QML.** L'updater ne vivait que dans
      l'ancienne fenêtre alors que l'installeur livre le shell QML : aucun
      utilisateur installé n'aurait été informé d'une nouvelle version. Surface
      dédiée (view-model + vue + entrée tray + vérification différée opt-out).
- [x] **AM-4 — Intégrité de l'installeur.** Le seul chemin qui exécute du code
      téléchargé ne vérifiait rien. URL contrainte aux hôtes GitHub (redirections
      comprises), SHA-256 publié vérifié avant lancement, répertoire privé.
- [x] **AM-12 — `downscale_width` appliqué.** Clé documentée mais morte :
      l'inférence tournait à la résolution native. `DownscaledFrameSource` branché
      avant la détection, avec preuve expérimentale que la pose de tête est
      invariante par changement d'échelle (dérive ~4e-6°).
- [x] **AM-16/AM-20 — Selfcheck et hygiène.** Le selfcheck QML sortait en succès
      alors que les view-models étaient collectés et que **toutes** les liaisons
      échouaient ; réparé, durci (les avertissements du moteur font échouer) et
      ajouté à la CI. Plus `CHANGELOG`, `SECURITY`, `CONTRIBUTING`, templates.

### Chantier honnêteté — vague 2 (qualité de détection & autonomie)

- [x] **AM-8 — Stabilité de l'utilisateur principal.** L'élection était calculée
      image par image, sans mémoire : deux personnes côte à côte se passaient le
      titre sur un micro-mouvement, et ce titre décide quel regard est ignoré.
      Hystérésis d'élection (marge + persistance) avec suivi du sortant par
      position, pas par indice de liste.
- [x] **AM-7 — Verrouillage d'absence.** Le scénario « je m'absente, quelqu'un
      s'installe » n'était structurellement pas couvert : avec un seul visage, ce
      visage *est* l'utilisateur principal. Troisième seuil, désactivé par défaut,
      avec la raison du masquage remontée à l'interface.
- [x] **AM-11 — Latence réglable.** `tracking` était absent de la config
      transmise au worker : le réglage n'y arrivait jamais. Corrigé, et exposé
      comme un curseur « Réactivité » plutôt qu'un coefficient d'EMA.
- [x] **AM-13 — Cadence.** Pause fixe qui s'ajoutait au traitement (15 fps
      demandés → ~11 fps réels) et charge constante. Régulation par échéance +
      repli au ralenti quand la pièce est vide.
- [x] **AM-10 — Géométrie d'écran.** Défaut 24 pouces contre un 13 pouces réel :
      rectangle presque quatre fois trop grand. Mesure système derrière un filtre
      de plausibilité pur ; asymétrie multi-écran documentée.
- [x] **AM-14 — Session verrouillée.** La caméra tournait derrière l'écran de
      verrouillage. Suspension/reprise (Windows, logind) ; macOS non implémenté et
      documenté comme tel.

### Chantier honnêteté — vague 3 (industrialisation)

- [x] **AM-5 — Dépendances verrouillées.** Bornes de majeures ≠ reproductibilité :
      lock universel épinglé et vérifié par empreinte pour la CI et le build.
- [x] **AM-6 — Release automatisée.** Sur tag : build verrouillé, modèle vérifié
      par empreinte, selfcheck du binaire **gelé**, installeur, `SHA256SUMS`
      publiés — sans quoi l'updater d'AM-4 ne peut rien installer.
- [x] **AM-17 — Chemin réel en CI.** Job non bloquant avec les extras vision et
      session réelle sur clip généré. A révélé que `ci.yml` ne parsait plus depuis
      la vague 1 ; les workflows ont désormais leurs propres tests.
- [x] **AM-18 — UI classic supprimée**, spec PyInstaller corrigée au passage.
- [x] **AM-9 — Regard iris**, implémenté et testé mais **désactivé par défaut** :
      non validé sur matériel, et se tromper coûte des faux positifs.
- [x] **AM-10b (partiel) — Correction manuelle** de la géométrie d'écran.
      L'assistant guidé reste à faire (validation matérielle indispensable).
- [x] **AM-19 (partiel) — Plateformes annoncées** dans le README. Le packaging
      macOS/Linux reste à faire.

Reste ouvert : assistant de calibration guidé, packaging macOS/Linux, et la
campagne de validation matérielle que la DoD attend toujours (§1).

---

## 5. Hypothèses prises (à défaut de blocage)

- **H1.** Config : on utilise **pydantic v2** + TOML (`tomllib` stdlib en lecture). Plus robuste
  pour la validation des bornes que des dataclasses nues.
- **H2.** Tracking : un **lissage exponentiel (EMA)** par défaut suffit au MVP ; un Kalman 1D
  optionnel est fourni pour les angles. On ne prétend pas à une précision sub-degré.
- **H3.** Géométrie : modèle simplifié — l'écran est le plan `z=0` face caméra ; le regard
  « pointe vers l'écran » si l'intersection du rayon de regard avec ce plan tombe dans les
  bornes de l'écran, avec une tolérance angulaire configurable (défaut généreux : ~15–20°,
  cohérent avec l'erreur webcam typique de 1,5–3° + marge).
- **H4.** Utilisateur principal = visage dont le centre est le plus proche du centre de l'image
  ET/OU le plus grand (proximité). Pondération configurable.
- **H5.** Masquage MVP = overlay plein écran (voile/pixelisation). Le flou de régions « sensibles »
  marquées est fourni comme stratégie mais le suivi de fenêtres par-OS est best-effort.
- **H6.** Seuils par défaut conservateurs : déclenchement après ~400 ms de regard tiers,
  levée après ~800 ms d'absence (anti-clignotement). Tous configurables.
- **H7.** MediaPipe et la webcam sont **optionnels au runtime** : absents → l'app log un
  avertissement et tourne en mode dégradé (overlay pilotable manuellement / par tests).
- **H8.** Aucune connexion réseau n'est jamais ouverte. Les modèles MediaPipe doivent être
  fournis localement (chemin configurable) ; aucun téléchargement automatique.

## 6. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| MediaPipe indispo en CI / sur la machine | bloque vision | abstraction + mode dégradé + tests sur stubs |
| Faux positifs (mouvements de tête) | masquage intempestif | hystérésis + seuils conservateurs configurables |
| Faux négatifs (mauvais éclairage) | fuite | doc honnête (LIMITATIONS) + sensibilité réglable |
| Latence trop élevée | masquage tardif | tests perf + downscale frame + skip frames |
| Overlay non click-through selon OS | gêne UX | interface OS + impl par défaut + best-effort Linux |
| Tentation de promettre l'invisibilité | malhonnête | règle d'honnêteté appliquée partout |

## 7. Ce qui n'est PAS protégé (résumé, détaillé dans LIMITATIONS.md)

- Un appareil qui **filme** l'écran (la caméra ne « voit » pas un objectif).
- Un observateur **hors champ** de la webcam.
- Les **reflets** (vitre, lunettes, miroir derrière l'utilisateur).
- Le **zoom à distance** / téléobjectif.
- La période de latence **avant** le masquage.

## 8. Ordre de développement (dépendances)

`config` → `geometry` → `tracking` → `policy` → `capture`/`vision` → `masking` → `overlay` → `app`.

TDD pour chaque module : **tests d'abord**, puis code, puis vert, puis lint/types, puis commit.
