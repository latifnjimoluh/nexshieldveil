# Contribuer à NexShieldVeil

## Les trois règles non négociables

1. **Honnêteté.** Aucun texte — code, commentaire, interface, documentation — ne doit
   laisser croire que le produit garantit la confidentialité. Il *réduit* le risque de
   regard indiscret. Un logiciel ne peut pas changer la direction dans laquelle la
   lumière quitte un écran.
2. **Rien ne sort de la machine.** Aucune image, aucun repère biométrique sur le
   disque ; aucune sortie réseau en dehors de `update/checker.py`, qui est
   explicitement mis en quarantaine et gardé par `tests/privacy/test_source_hygiene.py`.
   Un besoin légitime d'écrire un fichier (ex. l'entrée de démarrage automatique)
   s'ajoute à l'allow-list **avec sa justification et un test d'isolement**, jamais en
   affaiblissant la garde.
3. **Une fonctionnalité annoncée est une fonctionnalité câblée.** Un réglage visible
   dans l'interface doit agir. Si le câblage n'existe pas encore, la commande est
   grisée avec une mention explicite — elle n'est pas affichée comme active.

## Boucle de développement

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -e ".[dev,ui]"
pre-commit install

ruff check . && ruff format --check .
mypy src/privacy_guard/config src/privacy_guard/geometry src/privacy_guard/tracking \
     src/privacy_guard/policy src/privacy_guard/masking
pytest -m "not slow and not requires_hardware"
pytest -m privacy          # garanties de confidentialité
nexshieldveil --check      # selfcheck QML (câblage assemblé)
```

Toute la suite tourne **headless** : ni caméra, ni écran, ni modèle MediaPipe requis.

## Architecture : où mettre son code

La règle structurante du projet est la séparation **logique pure / adaptateurs
matériels**. Avant d'écrire dans un adaptateur, demandez-vous quelle part de la
logique peut en sortir :

- `config`, `geometry`, `tracking`, `policy`, `masking` — purs, typés strict
  (`mypy` strict), couverture attendue ≥ 95 %, testables sans matériel ;
- `capture`, `vision`, `overlay`, `ui/shell` — adaptateurs :
  minces, derrière une interface injectable et une garde d'import, dégradables.

Un module qui a besoin de matériel doit exposer sa *décision* dans un module pur.
`capture/resilience.py` (reconnexion caméra) et `overlay/compositor.py` (freeze-frame)
sont les modèles à suivre : zéro dépendance matérielle, 100 % testés.

## Dépendances

Les installations utilisateur gardent des bornes ouvertes (`pyproject.toml`), mais la
CI et le build installent un jeu **verrouillé et vérifié par empreinte** :

```bash
uv pip compile --universal --generate-hashes --extra dev --extra ui \
  --python-version 3.11 pyproject.toml -o requirements-ci.txt
```

À régénérer quand une dépendance bouge, ou quand `pip-audit` signale une CVE sur une
version épinglée — ce rouge est une invitation à mettre à jour, pas un bruit à faire
taire.

## Tests

TDD attendu : test d'abord, puis code. Un correctif **renforce** les tests, il ne les
affaiblit jamais. Les six niveaux existants (`unit`, `component`, `integration`,
`system`, `performance`, `privacy`) sont marqués via les marqueurs pytest déclarés
dans `pyproject.toml`.

Un test qui ne peut échouer ne vaut rien : quand vous ajoutez une garde, ajoutez aussi
le test qui prouve qu'elle attrape une violation plantée (voir
`test_guard_detects_a_planted_violation`).

## Commits et pull requests

- Commits conventionnels : `feat(scope):`, `fix(scope):`, `docs:`, `test:`, `ci:`,
  `build(release):`. Message en français, à l'impératif.
- Une PR = un sujet. Décrivez ce qui change, ce qui a été vérifié, et ce qui **n'a pas**
  pu l'être (typiquement : tout ce qui demande une vraie webcam ou un vrai écran).
- Mettez `CHANGELOG.md` à jour sous « Non publié ».
- La CI doit être verte : lint, format, mypy, bandit, pip-audit, tests, privacy,
  selfcheck QML.

## Ce qui reste hors périmètre

Reconnaissance d'identité des visages, rendu fovéal contingent au regard (approche B),
modulation psychovisuelle (approche C), et tout composant cloud. Voir
[`docs/ROADMAP.md`](../docs/ROADMAP.md) §2.
