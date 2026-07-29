# Politique de sécurité

NexShieldVeil est un logiciel de confidentialité : un défaut de sécurité ou de
confidentialité y est un défaut **fonctionnel**, pas un détail annexe.

## Signaler une vulnérabilité

Merci de **ne pas** ouvrir d'issue publique pour une faille exploitable.

Utilisez l'onglet **Security → Report a vulnerability** du dépôt GitHub
(*private vulnerability reporting*). Décrivez :

- ce que vous avez observé, et comment le reproduire ;
- la version (`nexshieldveil --version` ou le tag de la release) et le système ;
- l'impact que vous estimez.

Nous accusons réception sous **7 jours** et visons un correctif ou un plan de
correction sous **30 jours** pour tout ce qui est exploitable. Nous vous
créditerons dans le journal des modifications, sauf demande contraire.

## Périmètre

Sont particulièrement dans le périmètre :

- toute écriture d'image, de repère biométrique ou de gabarit facial sur le disque,
  ou toute sortie réseau depuis un module autre que `update/checker.py` (les gardes
  automatiques de `tests/privacy/` doivent le rendre impossible : un contournement
  est une faille) ;
- toute faiblesse du canal de mise à jour (URL non contrainte, empreinte non
  vérifiée, remplacement de l'installeur avant son lancement) ;
- toute élévation de privilège via l'installeur ou l'entrée de démarrage automatique ;
- tout moyen de faire lever le masquage à un observateur.

**Hors périmètre** — ce sont des limites connues et documentées dans
[`docs/LIMITATIONS.md`](../docs/LIMITATIONS.md), pas des vulnérabilités :

- un appareil qui filme l'écran, un observateur hors du champ de la webcam, les
  reflets, le téléobjectif ;
- la fenêtre de latence avant le masquage ;
- les faux négatifs en mauvaises conditions (éclairage, occlusion, angles extrêmes) ;
- la télémétrie propre à MediaPipe (dépendance tierce ; mitigation documentée dans
  [`docs/PRIVACY.md`](../docs/PRIVACY.md)).

## Versions supportées

Seule la dernière version publiée reçoit des correctifs de sécurité.
