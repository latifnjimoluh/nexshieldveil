# Backlog de remédiation — NexShieldVeil / `privacy-guard`

Priorisé du plus critique au plus faible. Effort indicatif :
**S** ≤ 1 h · **M** ≈ ½ j · **L** ≈ 1–2 j. Chaque correctif doit **renforcer** les
tests (jamais les affaiblir) et relancer toute la suite. Voir `docs/audit/AUDIT.md`.

> Aucun constat critique/élevé : il n'y a **pas** d'urgence de sécurité. Ce backlog
> vise à rendre le produit honnête et déployable.

## Priorité 1 — Moyennes (à traiter avant tout usage réel)

| # | ID | Action | Effort |
|---|---|---|---|
| 1 | ARCH-1 / CLAIM-1 / TEST-1 | **Décider et aligner le périmètre du masquage.** Option A : câbler une capture d'écran (`mss`) + `MaskStrategy` dans un renderer qui applique réellement `config.masking.strategy`, puis test d'intégration vérifiant la stratégie appliquée. Option B (plus rapide, honnête) : restreindre config + README au seul **voile**, retirer `pixelate/blur` (et `mss`) du périmètre annoncé. | A:L / B:M |
| 2 | CONC-1 | **Introduire la concurrence runtime.** Déporter capture+inférence dans un `QThread`/worker, lancer `app.exec()`, protéger l'état partagé (lock/signal Qt), et ajouter un smoke-test du chemin assemblé. | L |
| 3 | PRIV-1 / PRIV-2 / CLAIM-2 | **Renforcer les gardes de confidentialité.** Ajouter un test statique (AST/grep) échouant si `cv2.imwrite`/`socket`/`requests`/`urllib`/`os.open`(écriture) apparaît dans `src/` ; idéalement un job CI optionnel `[vision,ui]` rejouant une session réelle sous garde réseau/fichier. Nuancer `PRIVACY.md`. | M |
| 4 | DEP-1 | **Verrouiller les dépendances.** Committer un lock (`uv lock`/`pip-compile`) pour la CI, ou borner les majeures. | S |
| 5 | CI-1 / DEP-2 | **Durcir la CI.** Ajouter `bandit -r src` et `pip-audit` (dans un venv isolé) comme étapes bloquantes. | S |

## Priorité 2 — Faibles

| # | ID | Action | Effort |
|---|---|---|---|
| 6 | FUNC-1 | Documenter la latence effective (= `trigger_ms` + échauffement EMA) ; ou rendre l'EMA optionnel sur le signal binaire / exposer `alpha` et le seuil en config. | S |
| 7 | HYG-1 | Corriger le motif d'omit de couverture : `*/capture/webcam*` → `*/capture/opencv_sources*` (ou retirer l'omit). | S |
| 8 | ARCH-2 | Exposer `Kalman1D` via la config (choix EMA/Kalman) **ou** le retirer s'il reste inutilisé. | S |
| 9 | ARCH-3 | Retirer la dépendance `mss` tant que la capture n'est pas implémentée (lié au #1). | S |
| 10 | HYG-2 | Aligner le nom produit/paquet (`NexShieldVeil` ↔ `privacy_guard`) ou documenter l'alias. | S |
| 11 | CLAIM-1 / CLAIM-2 | Ajuster README/PRIVACY pour refléter l'état réel (couvert par #1 et #3). | S |

## Priorité 3 — Info (optionnel)

| # | ID | Action | Effort |
|---|---|---|---|
| 12 | FUNC-2 | Traiter `hit is None` (rayon parallèle) comme « non regardant » plutôt que repli sur le centre, par prudence ; ajouter le test du cas-limite. | S |

## Ordre d'exécution suggéré (un correctif = un commit)

1. **#4, #5** (verrouillage deps + CI durcie) — quick wins, base saine.
2. **#3** (gardes confidentialité + test statique) — protège la promesse centrale.
3. **#1** (périmètre masquage) — supprime la sur-promesse ; débloque #9/#11.
4. **#6, #7, #8, #10, #12** (nettoyage faible/info).
5. **#2** (concurrence) — chantier le plus lourd, à mener avec validation matérielle.

> Rappel de méthode (mode remédiation) : branche `audit/fixes`, un correctif par
> commit, du plus critique au plus faible, en **renforçant** les tests, suite complète
> relancée après chaque commit. Ne jamais mélanger audit et remédiation.
