# Livraison Prismora J-Lens Lab v0.2.0 — 14 juillet 2026

Cette livraison transforme le pipeline J-Lens v0.1 en un laboratoire local
unifié. Le même protocole expérimental peut être planifié pour Neuronpedia, un
worker GPU privé ou un backend synthétique de validation.

## Ce qui est réellement utilisable maintenant

- interface locale complète : protocoles, verrouillage, modèles, campagnes,
  runs, heatmaps, top-k, baselines, comparaison, interventions et registre de
  claims ;
- adaptateur Neuronpedia `/api/lens/prompt` en mode JSON bufferisé ;
- conservation des octets HTTP/source exacts et SHA-256 ;
- déduplication sans confondre des conditions différentes ;
- import des campagnes v0.1 `protocol.csv + raw/` ;
- sept protocoles scientifiques prêts à relire avant verrouillage ;
- worker HTTP neutre vis-à-vis du loueur GPU ;
- runtime réel, mais limité aux read-outs, fondé sur HuggingFace et le dépôt
  `jlens` d’Anthropic épinglé au commit public de juillet 2026 ;
- comparaison stricte Neuronpedia ↔ worker privé ;
- préflight GPU et gabarits Docker ;
- bundles reproductibles avec manifeste de hashes.

## Ce qui n’est pas présenté comme terminé

- aucun appel réel à Neuronpedia n’a été effectué pendant cette construction,
  faute de clé API ;
- le runtime HuggingFace/J-Lens n’a pas été chargé numériquement sur CUDA dans
  cet environnement ;
- les swaps, ablations, steering causal et ajustements de lentilles exigent
  encore un runtime GPU spécialisé et validé ;
- le laboratoire ne provisionne ni ne facture automatiquement un loueur GPU ;
  le plafond budgétaire doit aussi être défini chez le fournisseur.

## Premier ordre d’exécution recommandé

1. lancer les trois runs mock et télécharger leur bundle ;
2. effectuer un seul run Neuronpedia et contrôler le raw ;
3. créer le replay exact du filtre ;
4. exécuter les calibrations de fond précoce ;
5. lancer la campagne quadratique observationnelle ;
6. monter un petit worker Qwen avec une lentille pré-ajustée ;
7. effectuer le bridge strict public/privé ;
8. seulement ensuite développer les interventions causales.

Le rapport complet des validations est dans `TEST_REPORT.md`.
