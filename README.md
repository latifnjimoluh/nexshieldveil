# NexShieldVeil

> **Nommage :** le dépôt / produit s'appelle **NexShieldVeil** ; la distribution
> Python et le package importable sont `privacy-guard` / `privacy_guard`. C'est le
> même projet.

**Bouclier anti regard indiscret (anti shoulder-surfing).** NexShieldVeil surveille
ta webcam frontale et, dès qu'il détecte que **quelqu'un d'autre que toi** regarde
ton écran, recouvre automatiquement le contenu d'un **voile opaque** jusqu'à ce que
cette personne détourne le regard ou quitte le champ.

---

## ⚠️ Périmètre honnête — à lire en premier

Sur un écran standard, **un logiciel ne peut pas changer la direction dans laquelle
la lumière quitte l'écran.** Il n'existe aucun moyen de rendre un écran « invisible
de côté » en manipulant les pixels — c'est une **limite physique**, pas une
fonctionnalité manquante.

NexShieldVeil fait donc la seule chose qu'un logiciel peut faire : il **détecte un
observateur avec la caméra et cache le contenu**. Il **réduit** le risque de regard
indiscret ; il ne le **garantit pas**. Voir [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

Il **n'identifie jamais qui** est quelqu'un : il se contente de **compter / localiser**
les visages et d'**estimer** si un regard pointe vers l'écran — jamais de
reconnaissance faciale.

---

## 🔐 Confidentialité

- **Tout est traité localement, en RAM.** Le code de ce projet **n'écrit aucune image
  sur le disque** et **n'ouvre aucune connexion réseau** — c'est vérifié par une garde
  statique (AST) sur tout `src/` et par les tests `-m privacy`.
- **Aucun gabarit biométrique** n'est stocké ou transmis.
- ⚠️ **Nuance honnête sur les dépendances tierces :** la bibliothèque **MediaPipe**
  (Google) peut tenter d'émettre sa propre télémétrie (« clearcut ») — visible dans
  les logs. Ce n'est **pas** notre code, et la garantie « strictement local » couvre
  *notre* code. Pour un verrouillage total, bloque la sortie réseau du processus au
  pare-feu. Voir [`docs/PRIVACY.md`](docs/PRIVACY.md).

---

## ⚙️ Comment ça marche

```
webcam ─▶ capture ─▶ vision ─▶ geometry ─▶ tracking ─▶ policy ─▶ overlay
        (FrameSource) (visages + (le regard  (lissage)  (hystérésis  (voile on/off)
                       pose tête)  vise l'écran ?)        anti-flicker)
```

1. **capture** — récupère les images (webcam, fichier vidéo, ou source synthétique, injectable).
2. **vision** — MediaPipe Face Landmarker trouve les visages + estime la pose de tête (solvePnP).
3. **geometry** — choisit l'**utilisateur principal** (visage le plus central/proche) et teste,
   pour chaque **autre** visage, si son regard estimé pointe vers l'écran.
4. **tracking** — lisse le signal image par image (EMA) pour réduire le scintillement.
5. **policy** — machine à états à **hystérésis** : masque seulement après qu'un observateur
   ait regardé pendant `trigger_ms`, et démasque seulement après son absence pendant
   `release_ms` — ça évite le clignotement.
6. **overlay** — fenêtre Qt transparente, toujours au-dessus et « click-through », qui pose le voile.

Détails : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 📦 Installation

Requiert **Python 3.11+**.

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate   |   macOS/Linux : source .venv/bin/activate

# Cœur seul (logique pure ; ce que la CI exécute) :
pip install -e .

# Avec la webcam + l'UI (pour faire tourner l'application réelle) :
pip install -e ".[vision,ui]"

# Outils de dev (tests, lint, types) :
pip install -e ".[dev]"
```

### Le modèle MediaPipe

La détection a besoin d'un fichier modèle **Face Landmarker** local. NexShieldVeil
**ne télécharge jamais rien** — tu fournis le fichier. Télécharge
`face_landmarker.task` depuis la *model card* MediaPipe, place-le dans `models/`, et
pointe la config dessus :

```toml
[detection]
model_path = "models/face_landmarker.task"
```

Par défaut l'app cherche `models/face_landmarker.task`. Sans modèle (ou sans l'extra
`vision`), l'app démarre quand même en **mode dégradé** : elle ne voit aucun visage,
donc ne masque jamais, mais ne plante pas.

---

## ▶️ Utilisation

### 1. Application desktop (recommandé)

Interface **QML / Qt Quick** en architecture **MVVM** : l'app vit dans la **barre
d'état système** (tray) et ouvre à la demande des fenêtres soignées (réglages, à
propos, état). L'esthétique « verre dépoli » fait écho au voile qu'elle pose.

```bash
nexshieldveil                       # interface QML (barre d'état système)
nexshieldveil --config config.example.toml
nexshieldveil --light               # thème clair (défaut : sombre)
```

- **Icône de la barre d'état** — état lisible d'un coup d'œil : `Dégagé` / `Protégé`
  / `En pause` / `Erreur caméra`. Menu : bascule pause/reprise, **Ouvrir** (fenêtre
  d'état), **Réglages**, **À propos & limites**, **Quitter**.
- **Première exécution** — un onboarding honnête : ce que fait l'app **et ses
  limites**, puis une **demande de consentement caméra explicite** (la caméra ne
  s'ouvre qu'après ton accord), puis 2-3 réglages.
- **Indicateur « caméra active »** — visible dès que la caméra lit des images
  (exigence de transparence).
- **Réglages** — sensibilité du regard, délais de déclenchement/levée (hystérésis),
  style de masquage (seul le **voile opaque** est actif aujourd'hui ; flou /
  pixelisation sont marqués « bientôt »), opacité, caméra, démarrage à la session,
  **langue (FR/EN)** et **thème (clair/sombre)**.
- **Accessibilité** — contraste AA, focus clavier visible, tout opérable au clavier,
  `prefers-reduced-motion` respecté.

> L'ancienne fenêtre Qt Widgets (aperçu caméra + mises à jour intégrées) reste
> disponible le temps de la bascule : `nexshieldveil-classic` (ou
> `python -m privacy_guard.ui`).

> **Mises à jour & vie privée.** La vérification des mises à jour est la **seule**
> fonction qui contacte le réseau (GitHub) ; elle n'envoie **aucune donnée** et est
> totalement isolée de la caméra (voir [`docs/PRIVACY.md`](docs/PRIVACY.md)). La
> détection/masquage fonctionne, elle, **100% hors ligne**.

### 2. Ligne de commande sans interface (headless)

```bash
privacy-guard --config config.example.toml --verbose
```

Boucle de traitement sans fenêtre de contrôle (le voile Qt s'affiche quand même si
PySide6 est dispo). Utile pour un lancement minimal / au démarrage de session.

### 3. Scripts de test manuel (`scripts/`)

Outils de dev pour valider sur une vraie machine (non packagés) :

```bash
python scripts/run_live.py --solo-test   # voile + aperçu OpenCV, déclenche tout seul
python scripts/diagnose_gaze.py          # diagnostic SANS voile : imprime yaw/pitch/décision
```

Copie [`config.example.toml`](config.example.toml) pour régler timings, géométrie
d'écran, sensibilité et style de masquage.

> Besoin d'exécuter une commande dans ce shell ? Préfixe-la par `!`.

---

## 🛠️ Configuration

Tous les seuils sont configurables (et conservateurs par défaut). Principaux :

| Section | Clé | Défaut | Rôle |
|---|---|---|---|
| `[geometry]` | `gaze_tolerance_deg` | 18 | Tolérance d'angle « regarde l'écran » (= la sensibilité). |
| `[policy]` | `trigger_ms` | 400 | Durée de regard avant masquage. |
| `[policy]` | `release_ms` | 800 | Durée d'absence avant démasquage (≥ `trigger_ms`). |
| `[tracking]` | `smoothing_alpha` | 0.4 | Lissage EMA (1.0 = aucun, le plus réactif). |
| `[masking]` | `opacity` | 0.92 | Opacité du voile. |
| `[detection]` | `model_path` | — | Chemin local du modèle MediaPipe. |

---

## 🧪 Développement

```bash
pip install -e ".[dev,ui]"                 # dev tools + PySide6 (pour les tests d'UI)
ruff check . && ruff format --check .      # lint + format
mypy src/privacy_guard/config src/privacy_guard/geometry \
     src/privacy_guard/tracking src/privacy_guard/policy src/privacy_guard/masking
pytest -m "not slow and not requires_hardware"   # suite rapide (cœur + UI)
pytest tests/ui                                   # uniquement l'UI (view-models + QML)
pytest -m privacy                                 # garanties de confidentialité
pytest -m performance                             # benchmarks
pytest --cov=privacy_guard --cov-report=term-missing
bandit -r src -ll                                 # lint sécurité
pre-commit install                                # active les hooks
```

Toute la suite tourne **headless** (sans caméra ni écran). Le cœur s'injecte via
`SyntheticFrameSource` + `ScriptedFaceDetector` ; **l'UI** se teste via un
`FakeController` (stub de l'interface d'état) et le **plateforme Qt offscreen** :

```bash
# Les tests d'UI fixent QT_QPA_PLATFORM=offscreen automatiquement, mais en cas de
# besoin (ex. lancer un seul fichier QML) :
QT_QPA_PLATFORM=offscreen pytest tests/ui/test_views.py     # macOS/Linux
$env:QT_QPA_PLATFORM="offscreen"; pytest tests/ui/test_views.py   # Windows PowerShell
```

Les adaptateurs matériels (webcam, MediaPipe, fenêtres Qt) sont derrière des
interfaces injectables et des gardes d'import, donc dégradables. Sans l'extra `ui`
(PySide6), `tests/ui` est **ignoré** plutôt qu'en échec.

---

## 📁 Structure

```
src/privacy_guard/
  capture/  vision/  geometry/  tracking/  policy/  masking/  overlay/  config/
  ui/                  # frontend MVVM (PySide6)
    controller.py      #   AppController : contrat d'état observable cœur↔UI
    fake_controller.py #   stub pilotable (tests headless)
    core_controller.py #   implémentation réelle (worker thread → snapshot)
    state.py           #   enums + mappings purs (sans Qt)
    translator.py      #   i18n FR/EN commutable à chaud
    viewmodels/        #   QObjects testables (status, settings, onboarding, about, tray)
    views/             #   .qml (verre dépoli + transition « voile qui se pose »)
    theme/             #   tokens de design + ThemeController (sombre/clair, motion)
    i18n/              #   fr.json, en.json
    shell.py           #   lancement réel : tray + fenêtres QML
    control_window.py  #   ancienne UI Qt Widgets (fallback « classic »)
  app.py     # pipeline + CLI headless
scripts/     # run_live.py, diagnose_gaze.py (tests manuels matériels)
tests/       # unit/ component/ integration/ system/ performance/ privacy/ ui/
docs/        # ROADMAP ARCHITECTURE PRIVACY LIMITATIONS UI_PLAN DESIGN_TOKENS audit/
```

## Licence

MIT.
