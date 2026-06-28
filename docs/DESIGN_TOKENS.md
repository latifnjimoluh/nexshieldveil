# Tokens de design — NexShieldVeil

> Source de vérité du langage visuel. Décliné en `ui/theme/Theme.qml` (singleton QML)
> et reflété dans `ui/theme/tokens.py` (mêmes valeurs, testées pour parité et contraste).

## Élément signature : le voile (verre dépoli / profondeur floutée)

Le produit **pose un voile**. L'interface fait écho à ce geste : ses surfaces sont
des **panneaux de verre dépoli** (fond flouté + fine bordure lumineuse), et la
transition « la protection s'active » est un **voile qui se pose** — une montée
d'opacité + un léger flou + un infime tassement d'échelle, comme du givre qui prend
sur une vitre. L'esthétique de l'UI **est** une démonstration discrète de ce qu'elle
fait. C'est le seul endroit où l'on dépense de l'audace ; tout le reste est sobre.

Justification : c'est spécifique au sujet (pas un habillage générique), c'est
réutilisable (panneaux, overlay, onboarding partagent la même matière), et la
métaphore « lumière diffusée par un verre dépoli » dicte naturellement la palette
(teintes froides, lumineuses, **non néon**).

## Palette

Une teinte froide « ardoise » + **un seul** accent : un aqua diffus, la couleur de la
lumière qui traverse un verre dépoli. Pas de noir pur, pas de néon.

### Thème sombre (par défaut)
| Token | Hex | Rôle |
|---|---|---|
| `base` | `#13161B` | fond application (ardoise très sombre, **pas** `#000`) |
| `panel` | `#1C212A` | base des panneaux de verre dépoli (avec flou + transparence) |
| `line` | `#2C333F` | filets, séparateurs, bordures basses |
| `ink` | `#EAEEF4` | texte principal |
| `inkSoft` | `#9CA7B6` | texte secondaire |
| `accent` | `#74C7D6` | accent unique (aqua diffus) — focus, sélection, état actif |

### Thème clair
| Token | Hex | Rôle |
|---|---|---|
| `base` | `#EEF1F5` | fond (blanc embrumé bleuté, verre dépoli au jour) |
| `panel` | `#F7F9FC` | panneaux |
| `line` | `#D3DAE3` | filets |
| `ink` | `#1B2129` | texte principal |
| `inkSoft` | `#5A6675` | texte secondaire |
| `accent` | `#1F7E92` | accent (aqua plus profond pour le contraste sur clair) |

### Couleurs d'état (sémantiques)
Choix volontaire : **« Protégé » n'est pas alarmant** (la protection active est une
bonne nouvelle) ; l'alarme est réservée à ce qui demande une action (pause, erreur).

| État | Sombre | Clair | Sens |
|---|---|---|---|
| `clear` (Dégagé) | `#5FB58E` | `#2E7D5B` | tout va bien, surveillance active |
| `protected` (Protégé) | `#74C7D6` | `#1F7E92` | voile posé (= l'accent) |
| `paused` (En pause) | `#D9A441` | `#9A6B12` | attention : ne protège pas |
| `error` (Erreur) | `#E0736A` | `#B4453C` | action requise |

Contraste : tous les couples texte/fond visent **WCAG AA** (≥ 4.5:1 corps, ≥ 3:1
gros texte / éléments d'UI). Vérifié par test (`tests/ui/test_design_tokens.py`).

## Typographie

Trois rôles, trois faces **délibérément distinctes**, toutes à licence libre (SIL OFL).
Pas de « tout-en-Inter ».

| Rôle | Face | Licence | Usage |
|---|---|---|---|
| Display (caractériel, parcimonie) | **Space Grotesk** | OFL | grands libellés d'état, titres d'écran, hero onboarding |
| UI / corps (très lisible) | **Inter** | OFL | texte d'interface, libellés, descriptions |
| Mono / utilitaire | **JetBrains Mono** | OFL | valeurs techniques : °, ms, opacité, raccourcis |

Échelle typographique (px) : `12 · 14 · 16 · 20 · 26 · 34`. Display ≥ 26 uniquement.

## Espacement

Base 4. `space = [2, 4, 8, 12, 16, 24, 32, 48]` → `xxs xs sm md lg xl xxl xxxl`.

## Rayons & profondeur

- Rayons : `sm 8 · md 14 · lg 20 · pill 999`. Le verre dépoli veut des coins généreux.
- Profondeur : pas d'ombres dures. Une **lueur de bord** (1px `accent` à faible alpha)
  + un flou d'arrière-plan (`backgroundBlur`) signalent l'élévation, fidèles à la matière.

## Motion

| Token | Durée | Courbe | Usage |
|---|---|---|---|
| `quick` | 120 ms | `easeOutCubic` | survols, pressions |
| `standard` | 200 ms | `easeInOutCubic` | transitions d'état d'UI |
| `veilSettle` | 420 ms | `cubic-bezier(0.22,1,0.36,1)` | le voile qui se pose (opacité↑ + flou↑ + échelle 1.02→1.0) |

**`prefers-reduced-motion` (plancher non négociable)** : si activé, toutes les
transitions tombent à un simple **fondu d'opacité instantané/court** (≤ 80 ms), sans
échelle ni flou animé. Exposé par `Theme.reducedMotion` et respecté partout.

## Accessibilité (plancher)

- Contraste AA (testé sur les couples réels).
- **Focus clavier visible** : anneau `accent` 2px, jamais supprimé.
- Toutes les commandes opérables au clavier ; ordre de focus logique.
- Libellés accessibles (`Accessible.name`/`role`) sur chaque contrôle.
- `prefers-reduced-motion` respecté.

## Auto-critique (avant code) — défauts d'IA évités

Le brief §5 nomme trois facilités. Vérification :

1. **Crème + serif contrasté + terracotta** → écarté : palette froide ardoise/aqua,
   pas de terracotta, pas de fond crème.
2. **Quasi-noir + accent néon (vert acide / vermillon)** → c'est *le* piège des outils
   « privacy/sécurité ». Écarté **délibérément** : fond `#13161B` (ardoise, pas noir
   pur) et accent `#74C7D6` (aqua **diffus, désaturé**, pas néon). Aucun vert acide,
   aucun vermillon.
3. **Mise en page « journal » à filets fins sans arrondis** → écarté : matière verre
   dépoli, coins généreux (14–20px), profondeur par flou et non par filets.

**Révisions effectuées pendant la critique :**
- L'idée initiale d'un **« Protégé » rouge** (copié de la sémantique détection du cœur,
  où `MASKED` = rouge) a été **abandonnée** : en langage UI, protection active = état
  *rassurant*. Le rouge/coral est réservé à l'**erreur**. Cela évite d'alarmer
  l'utilisateur quand l'app fait exactement son travail.
- Première intention « display = serif Fraunces » **changée** pour Space Grotesk :
  une display serif sur fond sombre glissait vers le défaut (1)/registre « éditorial ».
  Un grotesque géométrique colle mieux à un outil système et reste caractériel.
- Tentation d'ombres portées marquées **retirée** : elles contredisent la matière
  « verre dépoli ». Profondeur = flou + lueur de bord uniquement.

Règle de retenue : l'audace est concentrée sur le **voile** (overlay + transitions).
Partout ailleurs : discipline, peu de couleur, rien de décoratif qui ne serve l'état.
</content>
