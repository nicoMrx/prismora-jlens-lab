# Prismora — système typographique

## Spectral — la voix

Utilisée pour :
- titres principaux ;
- titres de sections ;
- phrases-clefs ;
- annotations en italique ;
- « non mesuré », « silence » et autres formulations interprétatives.

Graisses privilégiées : 300, 400, ponctuellement 500.

## Albert Sans — le guide

Utilisée pour :
- menus ;
- boutons ;
- formulaires ;
- textes d’interface ;
- explications et aides ;
- fenêtres de réglages.

Graisses privilégiées : 400, 500 et 600.

## Spline Sans Mono — la mesure

Utilisée pour :
- tokens ;
- probabilités ;
- hashes ;
- rule_id et template_id ;
- numéros de couches ;
- données techniques courtes.

Graisses privilégiées : 400 et 500.

## Règle de production

Le prototype charge Google Fonts pour la revue visuelle.

Dans Prismora en production, Codex devra :
1. embarquer les WOFF2 dans `web/assets/fonts/` ;
2. synchroniser les mêmes fichiers dans `prismora_lab/assets/web/assets/fonts/` ;
3. ajouter les fichiers de licence OFL ;
4. déclarer les familles avec `@font-face` et `font-display: swap` ;
5. supprimer toute dépendance Google Fonts/CDN ;
6. conserver les fallbacks système.
