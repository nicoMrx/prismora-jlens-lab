# Rapport de correction Prismora — passe bornée 0.2.1

Date de la passe : 2026-08-13
Portée : copie reconstruite des six archives auditées
Règle appliquée : correction des défauts reproduits ou confirmés avec certitude, sans refonte du modèle scientifique ou produit

## 1. Provenance et préservation des sources

Les six archives d'entrée ont été lues puis assemblées dans un nouvel arbre. Elles n'ont pas été modifiées. Les métadonnées Finder sans rôle applicatif (`.DS_Store` et `__MACOSX`) n'ont pas été recopiées. Les SHA-256 des entrées sont conservés dans `SOURCE_ARCHIVES_SHA256.txt` :

| Source logique | SHA-256 |
|---|---|
| `01_core.zip` | `bc30460753b18753be43ab4567dd2830cefc8aaa8acd54c9af3618ce31e359f6` |
| `02_tests.zip` | `f41e981df05012c85f4661c76245c0d40780d97bf9d5b8b98225302739f3c7a6` |
| `03_worker.zip` | `e780af76773ed61f16277e1087e30c62166bf9df63b1c21d9600fa686c6da35c` |
| `04 frontend.zip` | `1e4327652b48ee8cd345b81497d22f3907c9f5e45cd23496c85e332028d7e09f` |
| `05_contracts-data.zip` | `ee9b737427147c31ebbce08cb9a3d3448eaa66cc890e0f889923b9cfc77f3b0f` |
| `06_docs.zip` | `34eea73fd89079dd33828b2287a4b37dbf2700ff6850561387dcfb3f88f1b3d8` |

La reconstruction est décrite dans `ASSEMBLY.md`. Les dossiers de travail générés (`.venv`, `.pytest_cache`, `.prismora-data`, `__pycache__`, `*.egg-info`, `build`, `dist`) ne font pas partie de l'archive livrée.

## 2. Corrections effectuées

### 2.1 Traversée de chemin et identifiants

**Défaut confirmé par lecture :** plusieurs identifiants reçus par les API étaient interpolés dans des chemins sans validation commune. Un identifiant contenant des séparateurs ou `..` pouvait sortir du répertoire logique attendu.

**Correction :** ajout d'une validation centralisée par liste blanche, sans réécriture silencieuse susceptible de créer des collisions. Les identifiants d'expérience, de run, de claim et de campagne sont contrôlés à toutes les frontières de stockage. Les schémas de run reprennent les mêmes motifs. `raw.relative_path` est résolu puis vérifié comme descendant strict du store avant toute lecture.

**Tests de régression :** identifiants Unix/Windows, chemins absolus, caractères joker, chemin raw sortant du store et absence d'écriture hors racine.

**Fichiers principaux :** `prismora_lab/identifiers.py`, `prismora_lab/store.py`, `prismora_lab/campaign_store.py`, `schemas/run-artifact-v2.schema.json`, miroir packagé du schéma, `tests/test_storage_integrity.py`.

### 2.2 Cohérence raw / raw_bytes / artifact et chaîne de hashes

**Défauts reproduits et confirmés :**

- `raw_bytes` pouvait être archivé tandis qu'un objet `raw` différent servait à construire le résultat normalisé ;
- les hashes internes d'un artefact n'étaient pas systématiquement recalculés ou contrôlés à l'écriture et à la lecture ;
- le post-traitement du live chat modifiait le résultat après calcul du hash canonique ;
- huit artefacts de démonstration contenaient des hashes `request_sha256` ou `canonical_result_sha256` qui ne correspondaient pas à leur contenu embarqué.

**Correction :** pour tout contenu déclaré JSON, les octets sont parsés et comparés canoniquement à l'objet normalisé avant écriture. Les hashes de requête, résultat canonique et raw sont contrôlés ; la taille raw est contrôlée quand les octets sont présents. Le post-traitement live intervient avant le hash final et avant le commit. Les hashes dérivables des huit démos ont été recalculés à partir de leur contenu, puis leurs manifestes externes ont été régénérés. Le script de maintenance refuse implicitement de fabriquer un `raw_sha256` sans disposer des octets source.

**Tests de régression :** divergence `raw`/`raw_bytes`, altération du résultat après stockage, cohérence des huit artefacts et des deux manifestes, hash live chat, absence d'orphelin après validation échouée.

**Fichiers principaux :** `prismora_lab/normalize.py`, `prismora_lab/store.py`, `prismora_lab/live_chat.py`, `scripts/recompute_artifact_hashes.py`, les huit artefacts sous `demo/`, leurs deux manifestes et leurs miroirs packagés, `tests/test_storage_integrity.py`, `tests/test_demo_internal_hashes.py`, `tests/test_live_chat.py`.

### 2.3 Immuabilité et écritures concurrentes

**Défauts reproduits et confirmés :** le schéma « tester l'existence puis remplacer » n'était pas un create-if-absent atomique. Deux producteurs pouvaient gagner la même course. Raw et artifact étaient publiés séparément, donc une interruption ou une course pouvait exposer une paire incomplète ou incohérente. Les API basses permettaient aussi de remplacer directement un run ou un protocole déjà verrouillé.

**Correction :** publication exclusive d'un inode terminé, commit atomique d'un répertoire de run préparé contenant `raw.json` et `artifact.json`, comportement idempotent uniquement lorsque tous les octets sont identiques, refus de toute autre réécriture. Les expériences et campagnes verrouillées sont immuables jusque dans les API de stockage. Les conflits sont exposés en HTTP 409.

**Tests de régression :** huit auteurs concurrents sur un fichier, deux runs concurrents de contenus différents, cohérence de la paire gagnante, réécriture de protocole verrouillé, lecture d'un artefact altéré.

**Fichiers principaux :** `prismora_lab/canonical.py`, `prismora_lab/store.py`, `prismora_lab/campaign_store.py`, `prismora_lab/api/app.py`, `tests/test_storage_integrity.py`, `tests/test_api.py`.

### 2.4 Matrices et couverture

**Défauts reproduits et confirmés :** une valeur de facteur pouvait devenir invalide seulement après son affectation dans `generation`, `readout` ou `intervention`, sans nouvelle validation. Des identifiants de run valides par composition pouvaient dépasser la longueur acceptée par le schéma. Une couverture marquée `complete` n'imposait ni l'équation source = transmis + tronqué, ni l'instrumentation de tous les tokens transmis. Des enveloppes de résultats vides étaient prises pour des mesures. Python acceptait en outre `true`/`false` comme compteurs entiers.

**Correction :** validation de la spec avant expansion puis de la requête liée après chaque combinaison ; identifiant déterministe borné à 160 caractères tout en conservant son suffixe de hash ; invariants arithmétiques et d'instrumentation exigés pour `complete` ; comptage basé sur des cellules `top_tokens` réellement présentes ; rejet explicite des booléens comme compteurs.

**Tests de régression :** `top_k=0` injecté par matrice, composants maximaux d'identifiant, couverture complète incohérente, instrumentation partielle et booléens.

**Fichiers principaux :** `prismora_lab/matrix.py`, `prismora_lab/coverage.py`, `tests/test_matrix.py`, `tests/test_build_week_understand.py`, `tests/test_storage_integrity.py`.

### 2.5 Comparaisons manifestement incorrectes

**Défauts reproduits et confirmés :** une comparaison bridge pouvait déclarer l'équivalence en ne comparant qu'un préfixe de deux vecteurs de probabilités de longueurs différentes. Le comparateur frontend local se limitait au top-1. La compatibilité dite stricte omettait des paramètres déterminants, les révisions et une partie du prompt.

**Correction :** toute différence de forme des probabilités invalide désormais l'équivalence et produit un avertissement compté. Le frontend compare les tableaux top-k et probabilités complets. La compatibilité stricte inclut l'identité modèle/tokenizer/lens, précision/quantification, génération, readout, couverture et prompt/chat complets ; une différence donne une comparaison partielle.

**Tests de régression :** préfixes numériques identiques mais longueurs différentes, différence hors top-1, prompt ou révision divergente, miroirs frontend synchronisés.

**Fichiers principaux :** `prismora_lab/analysis/compare.py`, `web/v4-user-comparison.js`, `web/v4-explorer-polish.js` et miroirs packagés, `tests/test_bridge_compare.py`, `tests/test_v4_user_comparison.py`, `tests/test_v4_comparison_compatibility.py`.

### 2.6 Paramètres déclarés mais non transmis

**Défauts reproduits et confirmés :** `generation.seed`, `generation.frequency_penalty` et `readout.exclude_first_n_positions` étaient acceptés par le contrat mais omis du payload Neuronpedia. Modifier `worker_url` dans la session changeait l'affichage, pas nécessairement le backend effectif. Une clé simplement configurée pouvait être présentée comme une connexion réussie.

**Correction :** transmission explicite vers `seed`, `frequencyPenalty` et `excludeFirstNPositions`, avec validation des types et bornes. Une modification de `worker_url` reconstruit le backend HTTP. « clé configurée » et « connexion testée avec succès HTTP 2xx » sont désormais deux états distincts, sans exposition de la clé.

**Tests de régression :** payload complet, rejets bool/float hors contrat, remplacement effectif du backend worker, réponses 401/403 non considérées connectées.

**Fichiers principaux :** `prismora_lab/backends/neuronpedia.py`, `prismora_lab/api/app.py`, `prismora_lab/session_security.py`, `README.md`, `tests/test_neuronpedia_adapter.py`, `tests/test_api.py`.

### 2.7 Révisions et paramètres du worker

**Défauts reproduits et confirmés :** le runtime de référence pouvait charger des références distantes non épinglées, son `runtime_id` ne couvrait pas toute la configuration, et plusieurs paramètres non entiers ou incompatibles pouvaient atteindre le GPU. Les IDs forcés n'étaient pas validés contre le vocabulaire. Un prompt trop long était tronqué silencieusement. `cached_token_ids` était accepté par le contrat sans implémentation effective.

**Correction :** révisions modèle, tokenizer et lentille obligatoires pour les références distantes ; identité du runtime issue de toute la configuration ; versions logicielles publiées ; cohérence entre requête et runtime vérifiée ; validation stricte des nombres, booléens, couches, types de readout et IDs ; contrôle de longueur avant transfert GPU ; aucun tronquage silencieux ; `cached_token_ids` refusé comme non pris en charge ; exclusion des premières positions effectivement appliquée et documentée dans la couverture ; filtrage des tokens de contrôle explicites.

**Tests de régression :** configuration non épinglée, identité de runtime, modèle/révisions incompatibles, couches booléennes/flottantes, IDs négatifs/hors vocabulaire, cache non pris en charge, overflow BOS/prompt, filtre Unicode et tokens de contrôle.

**Fichiers principaux :** `prismora_worker/hf_jlens_runtime.py`, `.env.gpu.example`, `tests/test_hf_jlens_runtime.py`.

### 2.8 Sérialisation effective du worker GPU

**Défaut confirmé par lecture et reproduit par test :** `max_batch_runs=1` était annoncé mais deux appels pouvaient entrer simultanément dans le même runtime et partager poids, hooks ou générateurs aléatoires.

**Correction :** verrou asynchrone autour de toute exécution du contrat worker, plus verrou interne du runtime HF autour de l'appel déporté dans un thread.

**Test de régression :** deux requêtes concurrentes instrumentées attestent que le maximum d'exécutions simultanées est un.

**Fichiers principaux :** `prismora_worker/app.py`, `prismora_worker/hf_jlens_runtime.py`, `tests/test_worker.py`.

### 2.9 Vulnérabilités frontend établies

**Défauts confirmés par lecture :** la fonction historique nommée `escapeText` n'échappait pas le HTML. Plusieurs valeurs dynamiques de couverture et de manifestes entraient dans `innerHTML` sans encodage, permettant l'interprétation de balises provenant de données importées.

**Correction :** échappement HTML réel pour les chaînes historiques ; échappement systématique des champs injectés dans les fragments de couverture ; construction DOM par `textContent` pour les données de manifestes showcase.

**Tests de régression :** marqueurs de payload HTML dans les champs dynamiques, vérification statique des sinks corrigés et syntaxe JavaScript de tous les fichiers.

**Fichiers principaux :** `web/app.js`, `web/v4-user-comparison.js`, `web/v4-showcase-insights.js` et miroirs packagés, `tests/test_v4_user_comparison.py`.

### 2.10 Packaging et build

**Défauts reproduits et confirmés :** le wheel n'embarquait pas l'arborescence frontend complète ni les démos ; les routes supposaient l'existence de répertoires adjacents à la source. Le numéro de version et l'étiquette UI étaient incohérents avec cette passe.

**Correction :** miroirs installables complets pour web, schémas, exemples et démos ; règles `package-data`/`MANIFEST.in` récursives ; fallbacks vers les assets du package ; version corrective `0.2.1` et étiquette `lab-v0.2.1-corrected` ; exemples d'environnement, ignore de build et documentation d'assemblage/provenance.

**Tests de régression :** présence et identité octet pour octet des trois arbres packagés, build wheel+sdist, installation du wheel hors source, réponses HTTP 200 pour `v4.html`, l'icône et les trois bibliothèques de démo.

**Fichiers principaux :** `pyproject.toml`, `MANIFEST.in`, `.gitignore`, `.env.example`, `.env.gpu.example`, `ASSEMBLY.md`, `SOURCE_ARCHIVES_SHA256.txt`, `README.md`, `CHANGELOG.md`, `VERSIONING.md`, `prismora_lab/api/app.py`, `prismora_lab/campaign_api.py`, `tests/test_packaging_layout.py`.

## 3. Fichiers ajoutés ou modifiés

Les miroirs packagés sont énumérés séparément car ils sont réellement présents dans la distribution et vérifiés octet pour octet.

### Ajoutés

- `.env.example`
- `.env.gpu.example`
- `.gitignore`
- `ASSEMBLY.md`
- `CORRECTION_REPORT.md`
- `SOURCE_ARCHIVES_SHA256.txt`
- `prismora_lab/identifiers.py`
- `scripts/recompute_artifact_hashes.py`
- `tests/test_demo_internal_hashes.py`
- `tests/test_packaging_layout.py`
- `tests/test_storage_integrity.py`

### Racine, build et documentation modifiés

- `CHANGELOG.md`
- `MANIFEST.in`
- `README.md`
- `VERSIONING.md`
- `pyproject.toml`

### Core modifié

- `prismora_lab/__init__.py`
- `prismora_lab/analysis/compare.py`
- `prismora_lab/api/app.py`
- `prismora_lab/backends/neuronpedia.py`
- `prismora_lab/campaign_api.py`
- `prismora_lab/campaign_store.py`
- `prismora_lab/canonical.py`
- `prismora_lab/coverage.py`
- `prismora_lab/live_chat.py`
- `prismora_lab/matrix.py`
- `prismora_lab/normalize.py`
- `prismora_lab/session_security.py`
- `prismora_lab/store.py`

### Worker modifié

- `prismora_worker/app.py`
- `prismora_worker/hf_jlens_runtime.py`

### Contrats et frontend modifiés

- `schemas/run-artifact-v2.schema.json`
- `prismora_lab/assets/schemas/run-artifact-v2.schema.json`
- `web/app.js`
- `web/index.html`
- `web/v4-explorer-polish.js`
- `web/v4-showcase-insights.js`
- `web/v4-user-comparison.js`
- `prismora_lab/assets/web/app.js`
- `prismora_lab/assets/web/index.html`
- `prismora_lab/assets/web/v4-explorer-polish.js`
- `prismora_lab/assets/web/v4-showcase-insights.js`
- `prismora_lab/assets/web/v4-user-comparison.js`

### Données et manifestes modifiés

- `demo/build_week_2026/MANIFEST_SHA256.json`
- `demo/build_week_2026/demo-pair-a-control.json`
- `demo/build_week_2026/demo-pair-a-shift.json`
- `demo/build_week_2026/demo-pair-b-control.json`
- `demo/build_week_2026/demo-pair-b-visible.json`
- `demo/showcase_2026/manifest.json`
- `demo/showcase_2026/showcase-meta-gpt-oss-observed.json`
- `demo/showcase_2026/showcase-meta-qwen-observed.json`
- `demo/showcase_2026/showcase-same-question-gpt-oss-final.json`
- `demo/showcase_2026/showcase-same-question-qwen.json`
- les dix fichiers correspondants sous `prismora_lab/assets/demo/`

### Tests modifiés

- `tests/test_api.py`
- `tests/test_bridge_compare.py`
- `tests/test_build_week_understand.py`
- `tests/test_cli_server_integration.py`
- `tests/test_hf_jlens_runtime.py`
- `tests/test_live_chat.py`
- `tests/test_matrix.py`
- `tests/test_neuronpedia_adapter.py`
- `tests/test_v4_comparison_compatibility.py`
- `tests/test_v4_user_comparison.py`
- `tests/test_worker.py`

Aucun fichier source n'a été supprimé.

## 4. Tests ajoutés ou adaptés

### Nouveaux fichiers de test

- `test_storage_integrity.py` : confinement des identifiants et chemins, cohérence raw, commit atomique, courses, protocoles verrouillés et détection d'altération.
- `test_demo_internal_hashes.py` : hashes internes des huit artefacts et hashes/tailles des manifestes.
- `test_packaging_layout.py` : contenu installable et identité des miroirs web/schémas/démos.

### Fichiers adaptés

- `test_api.py` : reconfiguration réelle du worker, sémantique de connexion et conflits d'immuabilité.
- `test_bridge_compare.py` : vecteurs de probabilités de longueurs différentes.
- `test_build_week_understand.py` : invariants renforcés de couverture, version corrective.
- `test_cli_server_integration.py` : port libre reproductible, client sans proxy d'environnement et arrêt déterministe du sous-processus.
- `test_hf_jlens_runtime.py` : révisions, identité, validations CPU et filtre.
- `test_live_chat.py` : hash calculé après enrichissement final.
- `test_matrix.py` : validation post-binding et longueur d'identifiant.
- `test_neuronpedia_adapter.py` : paramètres transmis et types stricts.
- `test_v4_comparison_compatibility.py` : identité de condition complète.
- `test_v4_user_comparison.py` : tableaux complets et sinks HTML.
- `test_worker.py` : sérialisation concurrente.

## 5. Vérifications exécutées

Résultats de la copie corrigée :

- `python -m pytest -q` : **160 tests réussis**, aucun échec ; un avertissement de dépréciation Starlette concernant l'ancien adaptateur `httpx` de `TestClient`.
- compilation syntaxique de tous les modules Python du projet et des tests : réussie.
- `node --check` sur tous les fichiers JavaScript de `web/` : réussi.
- parsing JSON de tous les `.json` livrés : réussi.
- build PEP 517 : wheel et sdist construits avec succès.
- installation forcée du wheel dans l'environnement de contrôle puis import depuis `/tmp`, hors arbre source : réussie.
- smoke HTTP depuis le wheel installé : `/v4.html`, `/assets/prismora-mark.svg`, `/api/demo/build-week`, `/api/demo/showcase` et `/api/demo/campaign-01` ont tous répondu **200**.
- contrôle du contenu du wheel : frontend imbriqué et manifestes de démo présents.
- contrôle final des six SHA-256 sources : identiques aux valeurs d'entrée.
- test d'intégrité de l'archive ZIP livrée : réussi.

Le build émet aussi une dépréciation Setuptools sur la forme table de `project.license`. Elle n'affecte pas le build actuel et reste classée en dette de packaging ci-dessous.

## 6. Éléments volontairement laissés ouverts

### Intégrité expérimentale et modèle scientifique

- **[Problème confirmé, décision d'architecture requise]** Le modèle `Experiment / Run / Attempt / Observation`, les réservations distribuées, les reprises et l'idempotence réseau ne sont pas refondus. Le commit local est atomique, mais la sémantique scientifique d'une tentative distante doit être décidée avant extension.
- **[Problème confirmé, décision scientifique requise]** Les artefacts ne sont pas encore liés de manière obligatoire au hash d'une spec verrouillée, au snapshot complet des capacités et au payload wire exact. Ajouter ces champs change le contrat scientifique et la compatibilité.
- **[Problème confirmé, hors périmètre demandé]** Les modèles de claims, baselines et NexusPrism/NexusMemory, leurs collisions d'identité et leurs règles d'évidence ne sont pas redéfinis.
- **[Risque non reproduit]** Le comptage de progression d'une campagne et la reprise après échec peuvent confondre artefacts présents, conditions planifiées et tentatives. Le correctif dépend du futur modèle de cycle de vie.
- **[Problème confirmé, décision scientifique requise]** Plusieurs champs d'analyse/préenregistrement sont descriptifs et ne sont pas tous exécutés comme règles automatiques d'exclusion ou d'arrêt.

### Provenance et données

- **[Risque non encore vérifiable]** Les octets raw externes des quatre exports showcase et certains raws de démonstration ne sont pas fournis. Leurs `raw_sha256` historiques ont été conservés, jamais recalculés ni déclarés vérifiés.
- **[Risque non encore vérifiable]** Les résumés de curation (`top_hits`, sous-ensembles de positions/couches et certaines couvertures) ne peuvent pas être recomputés intégralement sans les raws externes et le pipeline exact ayant servi à les produire.
- **[Problème confirmé]** Plusieurs exports réels ont des révisions modèle/tokenizer/lentille nulles. Les inventer aurait détérioré la provenance ; de nouvelles captures épinglées sont nécessaires.
- **[Décision scientifique requise]** La qualification d'indépendance des paires synthétiques et les différences de fixtures existantes n'ont pas été réécrites.
- **[Décision de gouvernance requise]** Consentement, licence, rétention et suppression des données utilisateur restent à formaliser.

### Worker, concurrence et sécurité

- **[Risque non reproduit]** Aucun modèle réel, CUDA ou `jlens` n'était disponible. Le chargement, les valeurs numériques, la mémoire GPU et l'équivalence bridge public/privé restent à tester sur l'environnement cible.
- **[Limite confirmée]** Les verrous garantissent une sérialisation par processus. Plusieurs processus Uvicorn, conteneurs ou replicas exigent un coordinateur GPU distribué ou une politique de déploiement mono-worker.
- **[Limite confirmée]** Les chemins locaux de modèle/lentille sont autorisés sans hash de contenu obligatoire. Leur stratégie de pinning dépend du déploiement.
- **[Problème confirmé, décision produit requise]** Le contrôle plane n'a pas d'authentification utilisateur intégrée et un `worker_url` configurable peut devenir une surface SSRF si l'application est exposée. Une politique réseau/allowlist dépend de l'architecture de déploiement.
- **[Limite de compatibilité assumée]** `cached_token_ids` est rejeté plutôt que simulé ; les interventions et le fitting restent explicitement non implémentés dans le runtime HF de référence.
- **[Risque non reproduit]** Les retries POST Neuronpedia n'ont pas de clé d'idempotence connue du fournisseur.

### Frontend et packaging

- **[Dette technique sans effet établi sur l'intégrité]** L'enregistrement des extensions par monkey-patch global de `FastAPI.mount`, l'empilement des scripts v4 et certains observers/patches globaux restent à simplifier.
- **[Risque fonctionnel]** Les imports frontend historiques ne constituent pas encore une frontière de confiance forte et peuvent manquer de provenance complète ; leur refonte dépend du contrat d'import.
- **[Limite confirmée]** L'alignement des tokens générés reste ordinal, pas sémantique. Les comparateurs l'annoncent désormais mais ne résolvent pas le problème scientifique.
- **[Problème confirmé, actif manquant]** Les trois fichiers `.woff2` fournis sont vides et les textes de licence de police sont incomplets. Aucun binaire ou texte de licence autoritatif n'était disponible ; les remplacer arbitrairement aurait été incorrect.
- **[Dette de packaging]** Il n'existe pas de lockfile de dépendances ni de digest final pour toutes les images. Les plages existantes ont été conservées faute de matrice de plateformes/support décidée.
- **[Dette de packaging]** La forme TOML actuelle de `project.license` est dépréciée par Setuptools mais encore supportée ; une migration future vers l'expression SPDX est non urgente.
- **[Dette documentaire]** `TEST_REPORT.md` reste le rapport historique 0.2.0. Il n'a pas été réécrit ; le présent fichier est l'enregistrement de la passe 0.2.1.

## 7. Compatibilité

Les changements suivants peuvent être observables :

- les identifiants qui ne respectent pas les motifs sûrs sont maintenant refusés, jamais normalisés silencieusement ;
- un run ou un raw existant ne peut plus être écrasé ; une répétition strictement identique est idempotente, toute différence produit un conflit ;
- les expériences et campagnes verrouillées sont immuables même via l'API basse ;
- les artefacts dont les hashes internes ou le raw présent ne correspondent pas sont refusés à la lecture/écriture ;
- un `raw_bytes` JSON différent de `raw` est refusé avant toute écriture ;
- une couverture `complete` anciennement tolérée peut devenir invalide si elle ne couvre pas tous les tokens transmis ou si ses comptes sont incohérents ;
- les matrices invalides après binding sont refusées ; seuls les identifiants qui auraient dépassé 160 caractères sont raccourcis de façon déterministe ;
- les comparaisons frontend peuvent passer de « stricte » à « partielle » quand une différence de condition auparavant ignorée est détectée ;
- le payload Neuronpedia contient désormais trois paramètres déjà déclarés par le contrat ;
- le worker HF exige des révisions pour les références distantes, refuse les caches non implémentés et les paramètres ambigus, et refuse les prompts trop longs au lieu de les tronquer ;
- le worker traite un run à la fois par processus, ce qui peut réduire le débit mais protège l'état GPU partagé ;
- le `runtime_id` change car il couvre désormais toute la configuration ;
- les hashes de requête/résultat des démos et les hashes de leurs fichiers dans les manifestes ont changé ; les `raw_sha256` historiques n'ont pas changé ;
- le numéro de paquet/API devient `0.2.1` et l'étiquette UI `lab-v0.2.1-corrected` ;
- le wheel embarque désormais les ressources nécessaires. Aucune fonctionnalité ni donnée métier n'a été supprimée.

## 8. Éléments correctement conçus et réutilisés

La passe conserve et réutilise les choix sains suivants : JSON canonique centralisé, SHA-256 explicites, conservation séparée des octets raw, schémas versionnés, expansion déterministe, verrouillage de préenregistrement par hash, abstraction de backend, mock déterministe, avertissements de couverture, conservation des duplicats avec qualification d'indépendance, contrats worker fournisseurs-neutres, manifestes de démo, export de bundles avec manifeste et séparation serveur/client des secrets.
