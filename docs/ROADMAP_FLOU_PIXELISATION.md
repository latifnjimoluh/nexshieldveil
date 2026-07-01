# Roadmap — Flou & pixelisation « live » (capture d'écran locale)

> Objectif : rendre les stratégies `blur` et `pixelate` **réellement appliquées à l'écran**
> au moment du masquage, au lieu du repli actuel sur le voile opaque.
>
> Document rédigé avant toute ligne de code, comme `docs/ROADMAP.md`, et tenu à jour.

---

## 1. État des lieux (analyse du code au 2026-07-01, v0.2.1)

### Ce qui existe déjà (et ne doit pas être réécrit)

| Élément | Fichier | État |
|---|---|---|
| Transformations pures `VeilMask`, `PixelateMask`, `BlurMask` | `src/privacy_guard/masking/strategies.py` | Implémentées, testées (~100 % de couverture), pur numpy, sans cv2 |
| Config `strategy` / `blur_radius` (1–199) / `pixelate_blocks` (2–256) | `src/privacy_guard/config/models.py` | Validée pydantic, bornée |
| Garde-fou honnête `overlay_strategy_is_live()` + `RUNTIME_OVERLAY_STRATEGIES = {"veil"}` | `masking/strategies.py` | C'est **l'interrupteur** à élargir à la fin du chantier |
| Overlay Qt plein écran, click-through, toujours au-dessus | `overlay/qt_overlay.py` | Peint un voile opaque + panneau (cadenas/message) ; **aucune capture** |
| Interface `Renderer` + `RecordingRenderer` (hook de test headless) | `overlay/renderer.py` | Le pipeline ne parle qu'à cette interface |
| UI : choix de stratégie (Réglages + Onboarding), mention « bientôt disponible » | `ui/viewmodels/settings.py`, `SettingsView.qml`, `OnboardingView.qml` | Branchée sur `overlay_strategy_is_live` — se mettra à jour seule |
| Plomberie MVVM `masking_strategy` (snapshot → contrôleur → VM → QML) | `ui/state.py`, `ui/controller.py` | Complète |
| Tests privacy : monkeypatch réseau/persistance + garde AST sur tout `src/` | `tests/privacy/` | À **étendre** à la capture d'écran, pas à contourner |
| Budgets perf (FPS pipeline, latence par frame) | `tests/performance/test_performance.py` | À compléter d'un budget « capture + transformation » |

### Ce qui manque (le cœur du chantier)

Pour flouter ou pixeliser le contenu réel, il faut **une image de l'écran**. Aujourd'hui
rien dans le code ne capture l'écran (choix délibéré, tracé dans `pyproject.toml` :
`mss` volontairement absent). Il faut donc :

1. un composant de **capture d'écran locale** (adaptateur, dégradable, testable via un fake) ;
2. un overlay capable d'**afficher une image** (le rendu actuel ne peint qu'une couleur) ;
3. l'**orchestration** : capturer *avant* d'afficher l'overlay (sinon on capture le voile),
   transformer hors du thread UI, échanger sans retarder le masquage ;
4. l'extension des **garanties de confidentialité** à la frame d'écran ;
5. l'ouverture du garde-fou `RUNTIME_OVERLAY_STRATEGIES` + textes UI/docs honnêtes.

---

## 2. Principes non négociables (hérités et étendus)

- **P1 — Le masquage instantané prime sur l'esthétique.** Si la capture ou la
  transformation prend du temps, le voile opaque s'affiche d'abord, immédiatement,
  et l'image floutée le remplace quand elle est prête. On ne retarde JAMAIS la
  protection pour la rendre plus jolie.
- **P2 — La frame d'écran est plus sensible que la frame caméra.** Elle contient le
  contenu à protéger. Elle vit uniquement en RAM, n'est jamais écrite sur disque,
  jamais envoyée sur le réseau, et est **libérée dès la levée du masque**.
- **P3 — Aucune capture continue.** On capture UNE image au moment du déclenchement
  (« freeze-frame »), pas un flux. Pas de capture en tâche de fond « au cas où ».
- **P4 — Dégradation propre.** Si la capture échoue (OS restrictif, écran verrouillé,
  Wayland sans portail), on retombe sur le voile opaque avec un avertissement loggé —
  jamais sur « pas de masquage ».
- **P5 — Honnêteté des textes.** Aucune promesse d'invisibilité. Les textes disent :
  « le contenu est flouté à partir d'une capture locale, jamais enregistrée ».
- **P6 — Pas de nouvelle sortie réseau, pas de télémétrie** (inchangé).
- **P7 — Le thread Qt ne bloque jamais.** La transformation (flou 1080p+) part dans
  un worker ; seuls la capture (rapide) et l'affichage restent sur le thread UI.

---

## 3. Choix d'architecture

### Option A — « Freeze-frame » : capturer 1 image, la transformer, l'afficher ✅ retenue

Au déclenchement : `capture écran (par moniteur) → afficher voile opaque immédiatement
→ transformer hors-thread → remplacer le voile par l'image floutée/pixelisée`.
À la levée : cacher l'overlay et **libérer l'image**.

- ✅ Aucune boucle de rétroaction (on capture avant d'afficher quoi que ce soit).
- ✅ CPU quasi nul une fois affiché ; une seule frame en mémoire.
- ✅ Le contenu affiché est figé : une notification qui arrive *pendant* le masquage
  reste cachée derrière l'image figée (bonus de confidentialité, à documenter).
- ✅ Réalisable **sans nouvelle dépendance** (voir choix de capture ci-dessous).
- ⚠️ L'image sous le masque est figée, pas « du vrai flou temps réel » — assumé et documenté.

### Option B — Flou temps réel (capture continue N fps) ❌ rejetée pour ce chantier

Exigerait d'exclure l'overlay de la capture (`SetWindowDisplayAffinity`/
`WDA_EXCLUDEFROMCAPTURE`, Windows 10 2004+ uniquement), une boucle capture-transformation
permanente (CPU/batterie), et violerait P3 (flux continu du contenu sensible en mémoire).
Aucun gain de protection réel par rapport au freeze-frame.

### Option C — Flou compositeur natif (acrylic/DWM « blur-behind ») ❌ rejetée

Le compositeur Windows flouterait derrière la fenêtre sans qu'aucun pixel n'entre dans
notre process (excellent pour P2), mais : API non documentée
(`SetWindowCompositionAttribute`), Windows-only, intensité non garantie (souvent trop
faible pour masquer du texte), et pas de pixelisation. Peut rester une piste
exploratoire post-chantier, jamais le mécanisme principal.

### Choix du mécanisme de capture

| Candidat | Verdict |
|---|---|
| **`QScreen.grabWindow(0)` (Qt, déjà présent via PySide6)** | ✅ **Retenu.** Zéro nouvelle dépendance, multi-écran (`QGuiApplication.screens()`), gère le DPI Windows, ~10–40 ms par écran — largement suffisant pour UNE capture au déclenchement. |
| `mss` | ❌ Pas nécessaire pour du freeze-frame. À reconsidérer seulement si un jour un flux continu devenait pertinent (il ne l'est pas, cf. Option B). |
| `PIL.ImageGrab` | ❌ Nouvelle dépendance (Pillow) sans avantage sur Qt. |

**Conséquence agréable :** pas de changement de dépendances, pas d'impact `pip-audit`,
et la garde AST privacy n'a pas de nouveau module tiers à évaluer.

---

## 4. Architecture cible

```
Déclenchement (policy → set_masked(True))
        │
        ▼
ScreenGrabber.grab_all()          # 1 QImage par écran, thread UI, ~10–40 ms/écran
        │        (échec → P4 : voile opaque simple, warning loggé)
        ▼
Overlay affiche le VOILE OPAQUE immédiatement (P1 — latence inchangée vs v0.2.1)
        │
        ▼
_MaskComputeWorker (QThread / QRunnable)   # P7
    QImage → numpy (H,W,3) → strategy.apply() → QImage
        │
        ▼ (signal Qt, thread UI)
Overlay remplace le voile par l'image transformée (fondu court, respecte reduced-motion)
        │
        ▼
Levée (set_masked(False)) → overlay caché → images capturée ET transformée libérées (P2)
```

Nouveaux modules (mêmes conventions que l'existant — interface pure + adaptateur exclu
de la couverture) :

```
src/privacy_guard/overlay/
    grabber.py       # interface ScreenGrabber + FakeScreenGrabber (testable headless)
    qt_grabber.py    # QtScreenGrabber via QScreen.grabWindow (adaptateur, no cover)
    compositor.py    # logique PURE : orchestre grab → veil-now → transform → swap
                     #   (états, choix de stratégie, gestion d'échec) — testée à fond
    qt_overlay.py    # étendu : peut afficher une QImage plein écran + multi-moniteur
```

`compositor.py` est le cœur testable : il reçoit un `ScreenGrabber`, une `MaskStrategy`
et un « présentateur » abstraits, et décide quoi afficher quand. Tout le raisonnement
(P1/P2/P4) se teste sans écran.

---

## 5. Jalons

### M-FP0 — Ce document
- [x] Commiter `docs/ROADMAP_FLOU_PIXELISATION.md` + pointeur dans `docs/ROADMAP.md`.

### M-FP1 — Performance des transformations (préalable, TDD)
Les impléms actuelles sont correctes mais pas calibrées pour du 1080p/4K :
- [x] Benchmark de référence : `BlurMask`/`PixelateMask` sur 1920×1080 et 3840×2160
      (marqués `performance`). Budget cible : **< 150 ms en 1080p, < 400 ms en 4K**
      (acceptable car le voile opaque couvre déjà l'écran pendant ce temps — P1).
      *Mesuré avant/après (machine de dev) : blur 1080p 231→75 ms, blur 4K
      1316→306 ms, pixelate 4K ~226 ms.*
- [x] `PixelateMask` : vectoriser (sommes de blocs `np.add.reduceat` sur les deux
      axes + `np.repeat` exact sur les comptes de blocs) — double boucle Python
      supprimée, tuilage identique (blocs de bord partiels inclus).
- [x] `BlurMask` : travail interne en `float32`, et **downscale → blur → upscale**
      pour les rayons larges. *Choix mesurés au micro-banc (le trafic mémoire domine) :
      downscale par accumulation de phases stridées (7,5× plus rapide que
      `reshape().mean()`), upsample bilinéaire par tranches de phases (vues décalées,
      zéro gather — les gathers pleine résolution étaient le goulot), padding de bord
      pour les tailles non divisibles, conversion uint8 fusionnée dans la passe finale.
      Écart vs blur direct pleine résolution : diff moyenne 0,7/255, p99 = 6 (bruit pur,
      pire cas) — testé unitairement. Les petits rayons restent sur le chemin direct
      (un flou faible masque peu ; ce n'est pas le cas à optimiser).*
- [x] Rester **pur numpy** (pas de cv2 dans le cœur — contrainte d'architecture existante).

### M-FP2 — Capture : interface + fake + adaptateur Qt
- [ ] `overlay/grabber.py` : `ScreenGrabber` (ABC) → `grab_all() -> list[ScreenShot]`
      où `ScreenShot = (image numpy (H,W,3) uint8, géométrie écran)`. +
      `FakeScreenGrabber` (images synthétiques, échec scriptable) pour tous les tests.
- [ ] `overlay/qt_grabber.py` : `QtScreenGrabber` — `QScreen.grabWindow(0)` par écran,
      conversion QPixmap → QImage → numpy **sans copie disque** (`pragma: no cover`,
      ajouté à l'`omit` coverage comme les autres adaptateurs display).
- [ ] Échec de capture (image vide/nulle, exception OS) → retour explicite, jamais
      d'exception non gérée (P4).
- [ ] Tests : contrat de l'interface via le fake ; garde AST privacy toujours verte
      (aucun nouvel import interdit).

### M-FP3 — Compositor (logique pure, le gros des tests)
- [ ] `overlay/compositor.py` : machine à petits états
      `IDLE → CAPTURED → VEILED(opaque) → TRANSFORMED(image) → IDLE`.
- [ ] Règles testées une par une :
      - le voile opaque est demandé **avant** toute transformation (P1) ;
      - la capture a lieu **avant** l'affichage du voile (sinon on capture le voile) ;
      - échec de capture → reste en voile opaque, log warning, pas de crash (P4) ;
      - stratégie `veil` → pas de capture du tout (comportement v0.2.1 inchangé) ;
      - levée du masque → les références aux images sont mises à `None` (P2, testé
        via `weakref`/comptage) ;
      - re-déclenchement pendant `TRANSFORMED` → PAS de nouvelle capture (l'overlay
        est visible, on garderait le voile) ;
      - transformation qui arrive APRÈS la levée (course) → jetée, pas affichée.
- [ ] Worker de transformation : `QThread`/`QRunnable` + signal résultat ; version
      synchrone injectable pour les tests déterministes.

### M-FP4 — Overlay : affichage d'image + multi-moniteur
- [ ] `_OverlayWidget` : nouveau mode « image » (peint une QImage plein écran) en plus
      du mode « voile » actuel ; le panneau cadenas/message reste par-dessus (l'utilisateur
      doit toujours comprendre POURQUOI son écran est masqué).
- [ ] Une fenêtre d'overlay **par écran** (`QGuiApplication.screens()`), chaque écran
      recevant sa propre capture transformée ; aujourd'hui seul l'écran principal est
      couvert — la correction vaut aussi pour le voile.
- [ ] Conserver : frameless, always-on-top, click-through, `WA_ShowWithoutActivating`.
- [ ] Fondu voile→image court (~120 ms), désactivé si `prefers-reduced-motion`.
- [ ] Test manuel scripté (`scripts/`) : vérification visuelle Windows (DPI 100 %/150 %,
      2 écrans si dispo) — documenté, hors CI.

### M-FP5 — Branchement pipeline + config + garde-fou
- [ ] `app.build_runtime_components` : construire le compositor quand la stratégie
      est `pixelate`/`blur` ; supprimer le warning de repli.
- [ ] Élargir `RUNTIME_OVERLAY_STRATEGIES` à `{"veil", "pixelate", "blur"}` — **en
      dernier**, quand tout le reste est vert : c'est l'interrupteur qui change l'UI
      (les mentions « bientôt disponible » disparaissent d'elles-mêmes) et le
      comportement runtime.
- [ ] Réglages UI : exposer `blur_radius` et `pixelate_blocks` (sliders bornés par la
      config pydantic existante 1–199 / 2–256) dans `SettingsView.qml` +
      `SettingsViewModel` + snapshot/contrôleur, avec aperçu textuel honnête.
- [ ] i18n FR/EN : nouvelles clés (descriptions des stratégies, mention « capture
      locale, jamais enregistrée », erreurs de capture) — parité testée comme aujourd'hui.

### M-FP6 — Confidentialité (extension des garanties, pas juste « pas de régression »)
- [ ] `tests/privacy/` : nouveaux tests dédiés à la frame d'écran :
      - aucun appel réseau pendant capture/transformation (fixtures existantes) ;
      - aucune écriture disque (le monkeypatch `np.save`/`imwrite`/`open(w)` couvre
        déjà, ajouter le chemin capture au périmètre exercé) ;
      - après `set_masked(False)`, plus AUCUNE référence vivante à la capture
        (test `weakref` sur le compositor) ;
      - pas d'accumulation : N cycles masquage/levée → mémoire stable.
- [ ] Garde AST : vérifier que `qt_grabber.py` passe la garde telle quelle (il le
      devrait : Qt seulement) ; ne PAS ajouter d'exception à la garde.
- [ ] `docs/PRIVACY.md` : nouvelle section « Capture d'écran au masquage » — quand,
      quoi, où ça vit, quand c'est libéré. `docs/LIMITATIONS.md` : l'image affichée
      est figée ; un flou reste une réduction de lisibilité, pas un chiffrement
      (un flou faible sur du texte très gros peut rester devinable → recommander les
      valeurs par défaut ou plus fortes).
- [ ] Onboarding/À propos : une phrase honnête sur la capture locale (P5).

### M-FP7 — Qualité, docs, release
- [ ] Gates complets : ruff, ruff format, mypy (étendre le périmètre strict à
      `overlay/compositor.py` et `overlay/grabber.py` — logique pure), bandit,
      pip-audit, pytest complet + privacy + performance.
- [ ] Couverture : `compositor.py`/`grabber.py` ≥ 90 % ; `qt_grabber.py` et le rendu
      dans l'`omit` (même règle que `qt_overlay.py`).
- [ ] `docs/ARCHITECTURE.md` + `docs/ROADMAP.md` (§ M7 note honnête) mis à jour.
- [ ] Version `0.3.0` (fonctionnalité visible) : `__init__.py`, `pyproject.toml`,
      `installer.iss` ; build PyInstaller + installeur Inno ; vérification `--check`
      + lancement réel ; release GitHub v0.3.0.

---

## 6. Ordre d'exécution et dépendances

`M-FP1 (perf transforms)` → `M-FP2 (grabber)` → `M-FP3 (compositor)` →
`M-FP4 (overlay image)` → `M-FP5 (branchement + UI)` → `M-FP6 (privacy)` → `M-FP7 (release)`.

M-FP1 est premier volontairement : inutile de brancher un flou qui prend 2 s en 4K.
M-FP6 court en réalité en continu (les tests privacy tournent à chaque commit), le
jalon ne couvre que les tests *nouveaux* et la doc.

---

## 7. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Capture lente sur certaines machines (4K, pilotes) | voile visible plus longtemps avant le flou | P1 : le voile opaque protège déjà ; budget perf testé ; downscale M-FP1 |
| On capture le voile (ordre inversé) | overlay flou du voile = gris uniforme | règle testée unitairement dans le compositor (M-FP3) |
| Écran verrouillé / UAC / DRM → capture noire ou échec | image noire floutée | détection d'image quasi uniforme → repli voile (P4) |
| Linux Wayland : `grabWindow` peut échouer sans portail | pas de flou sur Wayland | P4 : repli voile + note LIMITATIONS ; pas de dépendance portail pour l'instant |
| Fuite mémoire de la capture | frame sensible qui traîne en RAM | test `weakref` + test N-cycles (M-FP6) |
| Multi-DPI Windows (150 % + 100 %) | image décalée/étirée | géométrie par écran via Qt + test manuel scripté (M-FP4) |
| Flou trop faible = texte devinable | fausse impression de sécurité | bornes de config existantes + défauts costauds + LIMITATIONS (M-FP6) |
| Tentation du flux continu « plus joli » | violation P3 | option B explicitement rejetée ici ; toute réouverture = nouvelle roadmap |

---

## 8. Ce que ce chantier ne fait PAS (périmètre négatif)

- Pas de flou temps réel continu (Option B rejetée).
- Pas de flou par zones/fenêtres sensibles (suivi de fenêtres par OS = chantier séparé).
- Pas de nouvelle dépendance (`mss`, Pillow…) ni de nouvelle sortie réseau.
- Pas d'enregistrement, d'export ou d'aperçu utilisateur de la capture d'écran —
  l'image capturée n'est jamais montrée ailleurs que floutée/pixelisée dans l'overlay.
- Pas de changement des seuils/hystérésis de la policy (le déclenchement reste identique).
