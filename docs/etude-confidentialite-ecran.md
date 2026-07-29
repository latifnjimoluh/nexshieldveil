# Logiciel de confidentialité d'écran (anti-regard indiscret)
## Étude de faisabilité technique et plan de mise en œuvre

---

## 1. Résumé exécutif

L'objectif du projet est de protéger l'utilisateur d'un PC contre le **shoulder surfing** (regard indiscret d'une personne située à côté), de sorte que seule la personne placée face à l'écran puisse lire son contenu.

**Le verdict de faisabilité est nuancé et il faut le poser clairement avant tout développement :**

- L'idée intuitive — « un logiciel qui joue sur les pixels et la luminosité pour que l'écran soit invisible de côté » — **n'est pas réalisable en logiciel pur sur un écran standard.** C'est une limite physique, pas un manque de technologie (voir §2).
- En revanche, le *résultat recherché* (un voisin ne peut pas lire l'écran) est atteignable par logiciel via des approches qui exploitent **la perception humaine** et **la position/l'identité du regard**, pas la direction de la lumière. Trois architectures sont crédibles (§4).
- La solution la plus « logicielle » et la plus rapide à construire est la **détection d'observateur par caméra + masquage automatique** (Approche A). La plus robuste exige un accessoire matériel léger (lunettes synchronisées, Approche C).

En clair : on peut faire un produit utile et innovant, mais il faut abandonner la promesse d'une protection « 100 % logicielle et garantie » et la remplacer par une promesse honnête de **réduction forte du risque**.

---

## 2. Le verrou physique fondamental (à comprendre absolument)

Un écran (LCD ou OLED) fonctionne ainsi :

- Sur un **LCD**, un rétroéclairage émet de la lumière qui traverse un polariseur, une couche de cristaux liquides (qui module l'intensité pixel par pixel), des filtres de couleur, puis un second polariseur. L'angle de vue dépend du type de dalle (TN = étroit, IPS = large) et des films diffuseurs — tous **matériels**.
- Sur un **OLED**, chaque pixel émet sa propre lumière dans un large cône (émission quasi-lambertienne).

Dans les deux cas, **le logiciel ne contrôle que la valeur (intensité/couleur) de chaque pixel, jamais la direction dans laquelle les photons quittent la dalle.** Toute lumière qui forme une image lisible pour l'œil de face est aussi émise vers les côtés. On ne peut donc pas, par logiciel seul, « envoyer » l'image uniquement vers l'avant.

C'est exactement pour cette raison que les vraies solutions « angle de vue étroit » sont optiques :

- **Films de confidentialité 3M** : un réseau de micro-lamelles (comme un store vénitien microscopique) bloque physiquement la lumière oblique. Passif, permanent.
- **HP Sure View** (développé avec 3M) : version *commutable*. Un guide de lumière / rétroéclairage secondaire et un film à cristaux liquides collimatent la lumière vers l'avant quand on active le mode. Le déclencheur est logiciel (touche F2), mais **le mécanisme qui cache l'écran est matériel et optique**. Limite connue : l'effet faiblit quand on augmente la luminosité de l'écran.

**Conséquence pour le projet :** toute promesse de confidentialité par « manipulation de pixels » sur un écran ordinaire se heurtera à cette physique. Il faut concevoir le produit autour de ce qui est réellement possible.

---

## 3. Ce qui ne marchera pas (pièges à éviter)

Plusieurs idées séduisantes sur le papier échouent en pratique :

- **« Assombrir / brouiller selon l'angle. »** Le logiciel ne connaît pas l'angle d'un observateur sauf si une caméra le détecte (et alors on est dans l'Approche A). Il ne peut pas agir « par angle » tout seul.
- **« Couleurs complémentaires que seul l'œil de face recompose. »** L'œil d'un voisin recompose les couleurs exactement comme le vôtre ; rien dans la couleur ne dépend de la place de l'observateur sur un écran normal.
- **« Scintillement que seul l'utilisateur perçoit. »** Sans accessoire (lunettes), tous les yeux fusionnent les images de la même façon au-dessus de ~60 Hz. C'est précisément le principe que l'Approche C exploite — mais il exige des lunettes.

Garder ces points en tête évite de bâtir une feuille de route sur une base impossible.

---

## 4. Les trois approches réellement réalisables

### Approche A — Détection d'observateur + masquage automatique (la plus « logicielle »)

**Principe.** La webcam frontale surveille la scène. Un modèle de vision détecte les visages et estime la direction de leur regard. Dès qu'un *second* visage (autre que l'utilisateur) regarde l'écran, le logiciel **floute, masque ou réduit** le contenu sensible, puis le rétablit quand l'intrus disparaît.

**Atouts.** Aucun matériel autre que la webcam déjà présente. Concept éprouvé (de nombreux brevets, dont des dispositifs mobiles, décrivent « si quelqu'un regarde l'écran, on le masque »). C'est le meilleur point de départ pour un MVP.

**Limites.** Réactif (un court délai existe avant le masquage) ; ne protège que dans le champ de la caméra (~90–180°) ; inefficace contre une personne hors champ, un appareil photo à distance, ou un zoom ; faux positifs/négatifs selon l'éclairage et les mouvements de tête.

### Approche B — Rendu fovéal contingent au regard

**Principe.** On suit le regard de l'utilisateur autorisé avec la webcam. Seule la petite zone que son œil fixe (sa *fovéa*, ~2–5° de champ) est rendue nette ; tout le reste de l'écran est brouillé/bruité en temps réel. Comme un voisin ne sait pas où l'utilisateur regarde et que le reste est illisible, il ne peut pas reconstituer le contenu. L'utilisateur lit en déplaçant son regard : la fenêtre nette suit ses yeux.

**Atouts.** Protection plus forte que l'Approche A (le contenu hors-fovéa n'est jamais affiché en clair) et toujours sans accessoire (webcam seule). Fondé sur des travaux de recherche solides en *gaze-contingent / foveated rendering*.

**Limites (sérieuses).** La précision du suivi du regard par webcam est de l'ordre de **1,5–3° d'erreur**, avec dérive dans le temps et sensibilité aux mouvements de tête — contre 0,5–0,8° pour un traqueur infrarouge dédié (Tobii, EyeLink). La **latence** est critique : si la fenêtre nette est en retard sur l'œil, l'utilisateur voit du flou là où il regarde. Lecture ralentie et fatigue oculaire possibles. Mono-utilisateur. Vulnérable si un voisin filme et reconstruit plusieurs images.

### Approche C — Modulation psychovisuelle temporelle (TPVM)

**Principe.** Sur un écran à très haute fréquence (≥120 Hz, idéalement 240 Hz+), on affiche des « trames atomiques » qui se succèdent trop vite pour l'œil nu : à l'œil nu, elles se fondent en une image **leurre** (sans intérêt). L'utilisateur autorisé porte des **lunettes à obturateur à cristaux liquides synchronisées** qui pondèrent chaque trame ; son système visuel reconstitue alors la vraie image. Tout observateur à l'œil nu ne voit que le leurre.

**Atouts.** C'est la seule approche qui **cache vraiment le contenu à tout observateur sans lunettes**, y compris hors champ caméra. Garantie de confidentialité la plus forte des trois.

**Limites.** Exige un **accessoire matériel** (lunettes actives LC) et un **écran haute fréquence**. Donc « logiciel + lunettes », pas logiciel pur. Plus complexe à industrialiser (synchronisation, partenariat matériel).

### Tableau comparatif

| Critère | A — Détection + masquage | B — Rendu fovéal | C — TPVM (lunettes) |
|---|---|---|---|
| Matériel requis | Webcam (déjà là) | Webcam (déjà là) | Lunettes LC + écran ≥120 Hz |
| Force de la confidentialité | Moyenne | Élevée | Très élevée |
| Coût pour l'utilisateur (confort) | Faible | Élevé (fatigue, lecture lente) | Moyen (port de lunettes) |
| Complexité de développement | Modérée | Élevée (R&D) | Élevée (logiciel + matériel) |
| Protège contre un enregistrement / une caméra ? | Non | Partiellement | Oui (œil nu) |
| Adapté à un MVP rapide | **Oui** | Non | Non |

---

## 5. Architecture recommandée pour le MVP (Approche A, extensible vers B)

La recommandation est de livrer d'abord l'Approche A, conçue pour pouvoir greffer ensuite le mode fovéal (B) en option premium.

**Chaîne de traitement (pipeline temps réel) :**

1. **Capture caméra.** Flux webcam via l'API caméra de la plateforme (ou OpenCV).
2. **Détection de visages et de points de repère.** MediaPipe (Google, open source) — *Face Detection* + *Face Landmarker / Iris* — donne les visages, les yeux et l'iris en temps réel (~30–70 Hz sur CPU).
3. **Estimation du regard et de la pose de tête.** À partir des repères de l'iris et d'une estimation de pose (solvePnP/OpenCV), on calcule pour chaque visage un vecteur de regard et on détermine s'il pointe vers l'écran.
4. **Logique de décision + lissage.** Filtre de Kalman pour éviter le clignotement du masquage. Règle simple : si un visage *autre* que l'utilisateur principal a un regard dirigé vers l'écran pendant N millisecondes, déclencher le masquage.
5. **Couche de masquage (overlay).** Une fenêtre transparente toujours au premier plan floute/masque l'écran (ou seulement les fenêtres marquées « sensibles »).

**Réalité par système d'exploitation (le point le plus technique) :**

- **Windows :** fenêtre superposée (`WS_EX_LAYERED`, `WS_EX_TRANSPARENT`), capture de l'écran via *Desktop Duplication API*, flou appliqué sur GPU (shader), recomposition au-dessus du bureau. Certains contenus protégés (DRM) ne sont pas capturables — à signaler.
- **macOS :** `NSWindow` à niveau élevé + *ScreenCaptureKit* pour la capture, flou GPU.
- Le flou temps réel de contenu arbitraire est la partie difficile : prévoir un rendu **GPU** pour tenir la fréquence de l'écran sans latence visible.

**Performance visée :** traitement à la fréquence de l'écran, latence de masquage faible (idéalement < 200 ms après détection), usage CPU/GPU maîtrisé.

**Stack proposée :** Python (prototype) ou C++/Rust (production) pour la performance ; MediaPipe + OpenCV pour la vision ; couche native par OS pour l'overlay ; shaders (HLSL/Metal/GLSL) pour le flou.

---

## 6. Confidentialité et éthique du produit lui-même

Le logiciel utilise la caméra en permanence : c'est sensible. Principes à intégrer dès la conception :

- **Tout traiter en local.** Aucune image, aucun gabarit biométrique ne doit quitter l'appareil ni être stocké. Le flux caméra sert uniquement à la détection en mémoire vive, puis est jeté.
- **Pas de reconnaissance des tiers.** On détecte « un visage qui regarde », pas « qui est cette personne ». Cela évite de transformer un outil de protection en outil de surveillance.
- **Transparence.** Indicateur visible quand la caméra est active ; réglages clairs ; possibilité de désactiver.
- **Honnêteté commerciale.** Ne jamais vendre cela comme une garantie absolue. La promesse correcte est : « réduit fortement le risque qu'un voisin lise votre écran », avec les limites (caméras, angles, hors champ) écrites noir sur blanc.

---

## 7. Limites à assumer (ce que le produit ne protège PAS)

- Un appareil photo / smartphone qui **filme** l'écran (surtout avec zoom, ou hors champ de la webcam).
- Un observateur **placé derrière** l'utilisateur et hors du champ de la caméra.
- Les reflets de l'écran sur une vitre, des lunettes, etc.
- Les captures d'écran logicielles côté système (autre sujet, autre protection).

Documenter ces limites n'affaiblit pas le produit : c'est ce qui le rend crédible et défendable.

---

## 8. Feuille de route proposée

**Phase 0 — Preuve de concept (quelques semaines, 1 développeur).**
Détection de visage + estimation grossière du regard avec MediaPipe ; overlay simple qui floute tout l'écran dès qu'un second regard est détecté. Objectif : valider la latence et le taux de fausses alarmes.

**Phase 1 — MVP (plusieurs mois).**
Overlay performant (GPU), masquage ciblé sur les fenêtres sensibles, lissage anti-clignotement, calibration utilisateur, réglages de sensibilité, support d'un OS (Windows recommandé en premier), garde-fous de confidentialité.

**Phase 2 — Robustesse et second OS.**
Amélioration de la détection (conditions de lumière, multi-visages, mouvements), support macOS, optimisation énergétique, tests utilisateurs.

**Phase 3 (optionnelle) — Mode premium « fovéal » (Approche B).**
R&D sur le suivi du regard de l'utilisateur, le rendu fovéal temps réel et la gestion de la latence. À ne lancer qu'après validation des limites de précision webcam.

**Piste long terme — TPVM (Approche C).**
Pour une vraie garantie de confidentialité : partenariat matériel (lunettes LC synchronisées) + écran haute fréquence. À traiter comme un produit distinct, plus lourd.

---

## 9. Conclusion et recommandation

Le projet est **viable et pertinent**, à condition de remplacer l'objectif initial (« logiciel pur qui rend l'écran invisible de côté en jouant sur les pixels ») — impossible pour des raisons physiques — par un objectif atteignable : **détecter automatiquement les regards indiscrets et masquer le contenu sensible en temps réel.**

Recommandation concrète : démarrer par l'**Approche A** (détection caméra + masquage), seule voie réellement « logicielle » et la plus rapide à mettre sur pied, en l'architecturant pour accueillir plus tard le mode fovéal (B). Réserver la **TPVM (C)** à une version ultérieure avec accessoire matériel si une garantie de confidentialité forte devient nécessaire.

La clé du succès commercial sera l'**honnêteté de la promesse** : un outil qui réduit fortement le risque, pas un bouclier magique.
