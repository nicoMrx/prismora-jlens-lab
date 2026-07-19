# Kit maquette Prismora — de Fable pour Pepper (19/07/2026)

## Contenu
- `maquette/index.html` — LE prototype exécutable qui a produit la capture.
  Fichier unique (HTML+CSS+JS). S'ouvre dans un navigateur, tout est
  interactif : niveaux Lire/Explorer/Contrôler, thème sombre/clair,
  tokens cliquables, curseur de couches avec gap « non mesuré »,
  top-8, trajectoire, phrases Comprendre avec « Pourquoi ? », vue expert
  (heatmap avec cellules absentes, Claim Ledger, provenance).
- `design/prismora-design-tokens.css` — la matière exacte : variables des
  deux thèmes, rôles typographiques, rayons, ombres, variables de la
  marque (--pz-mark-a/b). Source de vérité couleur.
- `design/prismora-mark.svg` — le glyphe de Julie, optimisé 466 Ko → 8,7 Ko
  sans modification des tracés, couleurs tokenisées avec ses couleurs
  d'origine en fallback. Suit automatiquement les deux thèmes.

## Maquette v2 — les ajouts Photoshop de Julie sont intégrés
Le HTML contient désormais : le glyphe de Julie (symbol SVG réutilisé,
petit dans la barre à 38 px et grand dans le hero, couleurs qui suivent
les deux thèmes via --pz-mark-a/b), le wordmark à finale italique, et le
sélecteur de modèle en composant interactif — Qwen 3 et GPT-OSS
sélectionnables avec bascule API/local, Gemma volontairement désactivé
avec l'état « à venir » (aucune configuration au registre : pas de faux
bouton).

## Points techniques pour Codex
- Les polices du prototype passent par Google Fonts (CDN). Dans le dépôt,
  les VENDORER en local (woff2 + licences OFL dans web/assets/fonts/) —
  la démo juge doit fonctionner sans réseau.
- Les données du prototype sont synthétiques et codées en dur (calquées
  sur la paire A de la démo). Rien à réutiliser côté données.
- La section Git de PROMPT_CODEX_UI.md est OBSOLÈTE (écrite avant le
  merge de la PR #1) — le prompt de reprise de Pepper fait foi. Les
  jalons visuels T1–T5 et les contraintes (tokens = loi, honnêteté des
  vides, chemin juge intact, AA) restent valables comme référence.
- Gemma : aucune configuration au registre. Ne câbler AUCUN bouton tant
  que le modèle exact et sa source (Neuronpedia — vérifier la couverture
  Gemma/Gemma Scope par les endpoints jlens — ou local) ne sont pas
  définis. Un état « à venir » désactivé et honnête est acceptable.
