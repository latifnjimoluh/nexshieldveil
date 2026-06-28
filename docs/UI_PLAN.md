# Plan de l'interface — NexShieldVeil

> Document vivant. Il fixe les **surfaces**, les **flux**, le **contrat avec le
> cœur** et les **hypothèses** prises pour avancer sans bloquer. Mis à jour au fil
> de l'implémentation.

## 0. Hypothèses prises (faute de bloquant)

| # | Décision | Pourquoi | Conséquence si fausse |
|---|---|---|---|
| H1 | **Le frontend vit sous `src/privacy_guard/ui/`**, pas sous `src/nexshieldveil/ui/`. | Le package importable réel est `privacy_guard` (le dépôt/produit s'appelle NexShieldVeil — cf. note de nommage du README). Créer un 2ᵉ package top-level `nexshieldveil` casserait les imports, la couverture, le packaging et la cohérence. On garde **un** package. | Renommage mécanique ultérieur ; aucune logique à revoir. |
| H2 | **Vues en QML / Qt Quick**, view-models en Python (`QObject`). | Brief §3 : rendu moderne, MVVM strict, couture testable en Python. | — |
| H3 | L'UI **n'accède jamais directement** au cœur (`PrivacyGuardPipeline`, MediaPipe, OpenCV). Elle ne parle qu'à une **interface d'état** (`AppController`). | Découplage, testabilité headless, pas de duplication de logique (brief §3/§10.4). | — |
| H4 | Le **thread de capture/inférence reste hors UI** (déjà le cas : `QTimer`/`QThread` côté cœur). Les view-models ne font **aucun travail lourd**. | Brief §2 : ne jamais geler l'event loop. | — |
| H5 | Les préférences persistent via `QSettings` (déjà utilisé par l'updater). **Aucune** nouvelle écriture réseau/fichier image. | Cohérence avec l'existant ; contrainte vie privée. | — |
| H6 | L'ancienne `control_window.py` (Qt Widgets) est **conservée** comme chemin de repli legacy le temps de la bascule, puis l'entrée par défaut pointera vers la coquille QML. | Évite de casser `nexshieldveil`/`python -m privacy_guard.ui` pendant le chantier. | — |
| H7 | La langue par défaut suit la locale système, repli **FR** (public premier du projet), bascule FR/EN manuelle dans les réglages. | Le projet est rédigé en français ; EN requis par le brief §6. | — |
| H8 | « Style de masquage » dans l'UI n'expose honnêtement que ce qui est **réellement câblé** (voile opaque). Pixelisation/flou sont montrés comme **à venir** (désactivés/étiquetés), jamais comme actifs. | Brief §2 honnêteté + `overlay_strategy_is_live()` du cœur. | — |

## 1. Le cœur, tel qu'il est (ce sur quoi on se branche)

- `policy.PolicyState` = `CLEAR` / `OBSERVER_DETECTED` / `MASKED` (sémantique
  **détection**).
- `app.PrivacyGuardPipeline.step()` émet un `FrameResult` (scalaires : état,
  `is_masked`, `n_faces`, `observer_present`…) via un callback `on_result`. C'est
  **le hook observable** déjà prévu.
- `app.build_runtime_components()` dégrade proprement : pas de caméra → source vide ;
  pas de MediaPipe/modèle → détecteur aveugle ; pas de Qt → renderer d'enregistrement.
- `masking.overlay_strategy_is_live(strategy)` dit si une stratégie est réellement
  appliquée par l'overlay (aujourd'hui : `veil` seulement).

L'UI **ne réimplémente rien de tout ça**. Elle l'observe et lui envoie des commandes.

## 2. Le contrat UI ↔ cœur : `AppController`

Une interface mince et observable (un `QObject` abstrait), seul point de contact.

**État exposé (propriétés notifiables) :**

| Propriété | Type | Sens |
|---|---|---|
| `protection_state` | enum `ProtectionState` | `PROTECTED` / `CLEAR` / `PAUSED` / `CAMERA_ERROR` |
| `camera_active` | bool | la caméra est ouverte et lit des images **maintenant** |
| `error_kind` | enum `CameraError` \| none | `NO_CAMERA` / `DISCONNECTED` / `PERMISSION_DENIED` / `MODEL_UNAVAILABLE` |
| `faces_count` | int | nombre de visages vus (jamais d'image, jamais d'identité) |
| `masking_strategy` | str | stratégie configurée |
| `running` | bool | la surveillance tourne (≠ en pause) |

**Mapping `PolicyState` → `ProtectionState` (dans le contrôleur réel, pas l'UI) :**

```
running == False ............................. PAUSED
error_kind != none ........................... CAMERA_ERROR
is_masked (MASKED) ........................... PROTECTED
sinon (CLEAR / OBSERVER_DETECTED) ............ CLEAR
```

> `OBSERVER_DETECTED` est un **transitoire** (on est en train de déclencher) : l'UI
> le rend comme un sous-état visuel de `CLEAR` (« observateur repéré… ») sans changer
> l'état logique, pour éviter le scintillement d'icône.

**Commandes (slots) :** `enable()`, `pause()`, `toggle()`, `set_masking_strategy(s)`,
`set_sensitivity(deg)`, `set_trigger_ms(ms)`, `set_release_ms(ms)`, `select_camera(i)`,
`set_start_at_login(b)`, `open_settings()`, `quit()`.

**Signaux :** `state_changed`, `camera_active_changed`, `error_changed`,
`faces_count_changed`, `config_changed`.

**Stub :** `FakeController` implémente la même interface, pilotable à la main
(`emit_state(PROTECTED)`, `emit_error(NO_CAMERA)`…) pour tous les tests headless.
La logique de présentation est testée contre le **stub**, jamais contre le vrai cœur.

## 3. Surfaces (brief §4)

### 3.1 Barre d'état système (surface principale)
Icône qui reflète l'état d'un coup d'œil + menu.

```
┌─────────────────────────────┐
│ ● NexShieldVeil — Protégé    │   ← entête d'état (couleur + libellé)
├─────────────────────────────┤
│  ◐ Caméra active             │   ← indicateur transparence caméra
│  Visages vus : 2             │
├─────────────────────────────┤
│  ⏸  Mettre en pause          │   ← bascule (libellé miroir de l'état)
│  ⚙  Réglages…                │
│  ⓘ  À propos & limites       │
├─────────────────────────────┤
│  ⏻  Quitter                  │
└─────────────────────────────┘
```
Icône tray : 4 glyphes selon l'état (clair / voile posé / pause / erreur).

### 3.2 Première exécution / onboarding (3 volets)
```
 (1) Ce que fait NexShieldVeil        (2) Accès caméra            (3) Premiers réglages
 ┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
 │  « le voile »  [hero flou] │  │  ◐  Pourquoi la caméra ?   │  │  Style de masquage         │
 │                            │  │  Tout reste en local, en   │  │  ◉ Voile opaque            │
 │  Détecte un regard tiers   │  │  RAM. Aucune image n'est   │  │  ○ Flou (bientôt)          │
 │  et pose un voile.         │  │  enregistrée ni envoyée.   │  │  ○ Pixelisation (bientôt)  │
 │                            │  │                            │  │                            │
 │  ⚠ Ce qu'il NE protège pas │  │  [ Autoriser la caméra ]   │  │  ☐ Démarrer à l'ouverture  │
 │  (lien limites, explicite) │  │  [ Plus tard ]             │  │     de session             │
 │  [ Suivant → ]             │  │                            │  │  [ Terminer ]              │
 └───────────────────────────┘  └───────────────────────────┘  └───────────────────────────┘
```
Consentement explicite : la caméra ne s'ouvre **qu'après** le clic « Autoriser ».
Le volet 1 affiche les limites **avant** toute demande d'accès.

### 3.3 Réglages / préférences (onglets)
```
┌ Réglages ─────────────────────────────────────────────┐
│ [Détection] [Masquage] [Caméra] [Général] [À propos]   │
│                                                        │
│ Détection                                              │
│   Sensibilité du regard      [——●———] 18°  équilibré   │  (mono pour la valeur)
│   Délai avant masquage       [——●———] 400 ms           │
│   Délai avant levée          [———●——] 800 ms (≥ déclen.)│
│                                                        │
│ Masquage                                               │
│   Style    ◉ Voile opaque   ○ Flou*  ○ Pixelisation*   │  (* « bientôt », désactivé)
│   Opacité du voile           [————●—] 0.92             │
│                                                        │
│ Général                                                │
│   Raccourci bascule          [ Ctrl+Alt+V ]            │
│   ☐ Démarrer à la session    Langue [FR ▾]  Thème [◐]  │
└────────────────────────────────────────────────────────┘
```
Invariant repris du cœur : `release_ms ≥ trigger_ms` (validé, message clair).

### 3.4 Indicateurs discrets en usage
- **Pastille d'état** (coin, petite, non bloquante) : couleur + libellé court.
- **Indicateur « caméra active »** : visible dès que la caméra lit (transparence,
  brief §2). Disparaît en pause / erreur.

### 3.5 Traitement visuel de l'overlay
Le voile lui-même : esthétique « verre dépoli qui se pose » (motion `veil-settle`),
non agressif, respecte `prefers-reduced-motion` (apparition en simple fondu). Ne
dégrade pas les perfs du renderer ni la logique de détection (purement visuel).

### 3.6 À propos / Limites
Reprend `LIMITATIONS.md` : tableau honnête de ce qui **n'est pas** protégé, version,
licence, rappel « réduit le risque, ne garantit pas ».

### 3.7 États vides & erreurs (orientés action)
| État | Message (esprit) | Action |
|---|---|---|
| Pas de caméra | « Aucune caméra détectée. Branche une webcam pour activer la surveillance. » | Réessayer |
| Caméra déconnectée | « La caméra a été déconnectée. La surveillance est en pause. » | Reconnecter / Réessayer |
| Permission refusée | « NexShieldVeil n'a pas accès à la caméra. Autorise-le dans les réglages système. » | Ouvrir réglages système |
| MediaPipe/modèle absent | « Le modèle de détection est introuvable. La surveillance ne peut pas voir de visage. » | Voir la doc modèle |

Jamais vague, jamais culpabilisant.

### 3.8 Calibration du regard *(optionnel)*
Hors périmètre tant que le cœur ne l'exige pas (il ne l'exige pas aujourd'hui).

## 4. Flux principaux

1. **Premier lancement** → onboarding (limites → consentement caméra → 3 réglages) →
   tray actif.
2. **Usage nominal** : tray = `Protégé`/`Dégagé` ; le voile se pose/lève seul.
3. **Pause/reprise** : clic tray ou raccourci → `En pause` (caméra relâchée, indicateur off).
4. **Erreur caméra** : état `Erreur caméra` + message orienté action ; reprise auto si possible.
5. **Réglages** : modifient la config → `AppController.set_*` → cœur ; persistées.

## 5. Architecture des fichiers (cible)

```
src/privacy_guard/ui/
  controller.py       # AppController (interface) + ProtectionState/CameraError enums
  fake_controller.py  # stub pilotable (tests)
  core_controller.py  # implémentation réelle branchée au pipeline (hors couverture headless)
  app_qml.py          # bootstrap QApplication + QQmlEngine + enregistrement des VM
  viewmodels/         # QObjects testables : status, settings, onboarding, about, tray
  views/              # .qml : Tray, Onboarding, Settings, About, StatusPill, CameraBadge, Veil
  theme/              # Theme.qml (singleton tokens), Tokens.py (miroir Python pour tests)
  assets/             # icônes (générées/svg), polices à licence libre
  i18n/               # fr.json, en.json (clés à plat)
tests/ui/             # tests view-models + smoke vues + a11y + honnêteté + parité i18n
```

## 6. Tests (résumé, détail en §7 du brief)

Tout headless (`QT_QPA_PLATFORM=offscreen`). Le gros : view-models contre `FakeController`.
Smoke QML, pilotés par l'état, accessibilité, honnêteté de la copie, parité FR/EN.

## 7. Journal d'avancement

- **2026-06-28** — Lecture du cœur. Décisions H1–H8 figées. UI_PLAN + DESIGN_TOKENS
  rédigés et critiqués avant tout code (cf. DESIGN_TOKENS §« Auto-critique »).
</content>
</invoke>
