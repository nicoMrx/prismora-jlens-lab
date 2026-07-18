# Checklist du premier run réel

## Neuronpedia

- [ ] Copier `.env.example` vers un fichier local non versionné.
- [ ] Renseigner `NEURONPEDIA_API_KEY` côté serveur uniquement.
- [ ] Démarrer l’interface et vérifier la carte Neuronpedia dans **GPU / API fleet**.
- [ ] Charger `filter_nonword_bootstrap.json`.
- [ ] Vérifier le `model_id`, `top_k`, la longueur et le filtre avant verrouillage.
- [ ] Verrouiller le protocole.
- [ ] Exécuter un seul run.
- [ ] Télécharger l’octet brut exact et noter son SHA-256.
- [ ] Ouvrir la heatmap sans produire de claim scientifique.
- [ ] Créer le replay exact `inputTokenIds` du filtre.

## Worker GPU

- [ ] Choisir une image CUDA/PyTorch compatible avec le GPU loué et l’épingler par digest.
- [ ] Épingler révisions des poids, du tokenizer et de la lentille.
- [ ] Définir un token bearer long et aléatoire.
- [ ] Exécuter `prismora-worker-preflight`.
- [ ] Exécuter `prismora-worker-preflight --load`.
- [ ] Vérifier `/v1/health` et `/v1/capabilities` depuis le control plane.
- [ ] Faire un run privé court, sans intervention.
- [ ] Rejouer exactement les mêmes token IDs en public et en privé.
- [ ] Utiliser **Comparison Studio → strict public/private bridge**.
- [ ] Ne fusionner les corpus que si les divergences sont expliquées et documentées.

## Avant toute campagne coûteuse

- [ ] Plafond de dépense chez le fournisseur.
- [ ] Arrêt automatique de l’instance.
- [ ] Volume persistant ou transfert des raws avant extinction.
- [ ] Protocole verrouillé et règle d’arrêt écrite.
- [ ] Résultats nuls et réfutations conservés.
