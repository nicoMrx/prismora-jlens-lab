# Démarrage rapide — Prismora J-Lens Lab v0.2.0

## 1. Tester l’interface sans clé ni GPU

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m prismora_lab.cli serve
```

Ouvre ensuite `http://127.0.0.1:8000`.

Dans l’interface :

1. **Experiments** → charge `strategy_quadratic_mock.json`.
2. **Save draft**, puis **Lock protocol**.
3. **Campaign builder** → construis le plan et lance trois runs.
4. **Run inspector** → ouvre une heatmap et les top-k.
5. **Comparison studio** → compare deux conditions.
6. **Download evidence bundle** → récupère le ZIP reproductible.

Les données du backend mock sont synthétiques : elles testent le laboratoire,
pas le fonctionnement cognitif d’un modèle.

## 2. Brancher Neuronpedia

Dans le terminal qui lance le serveur :

```bash
export NEURONPEDIA_API_KEY='ta-cle'
python -m prismora_lab.cli serve
```

Charge ensuite `strategy_quadratic_01.json` ou
`filter_nonword_bootstrap.json`. Vérifie les identifiants de modèles disponibles
sur ton compte avant de verrouiller une campagne coûteuse.

Pour comparer proprement `filter_nonword_tokens` : fais d’abord un run source,
puis utilise **Baseline lab → Create exact filter replay**. Le protocole créé
réinjecte exactement tous les `inputTokenIds` et ne change que le filtre.

## 3. Tester le contrat cloud GPU

Terminal 1 :

```bash
export PRISMORA_WORKER_RUNTIME=mock
python -m prismora_worker.app --port 8100
```

Terminal 2 :

```bash
export PRISMORA_WORKER_URL=http://127.0.0.1:8100
python -m prismora_lab.cli serve
```

La carte **GPU / API fleet** doit montrer le worker disponible.

## 4. Brancher un vrai modèle open weights pour les read-outs

Installe les dépendances GPU, puis utilise le runtime de référence inclus :

```bash
python -m pip install -r requirements-gpu.txt
export PRISMORA_WORKER_RUNTIME='prismora_worker.hf_jlens_runtime:create_runtime'
export PRISMORA_HF_MODEL_ID='Qwen/Qwen3.5-4B'
export PRISMORA_HF_MODEL_REVISION='<commit exact>'
export PRISMORA_JLENS_NAME_OR_PATH='neuronpedia/jacobian-lens'
export PRISMORA_JLENS_FILENAME='<chemin exact du lens.pt>'
export PRISMORA_JLENS_REVISION='<révision immuable>'
export PRISMORA_WORKER_TOKEN='secret-long'
prismora-worker-preflight
prismora-worker-preflight --load
python -m prismora_worker.app --host 0.0.0.0 --port 8100
```

Lis `GPU_RUNTIME_REFERENCE.md`. Le fichier `Dockerfile.gpu.reference` fournit
également une base de déploiement neutre vis-à-vis du loueur. Ce runtime permet
les lectures Jacobian/Logit
et le rejeu exact de tokens. Il refuse encore les interventions et l’ajustement
de lentilles. Pour ces fonctions, pars de `prismora_worker/runtime_template.py`
et suis `CLOUD_GPU_GUIDE.md`.

## 5. Tests

```bash
python -m pytest
```

Le rapport de validation de cette livraison est dans `TEST_REPORT.md`.
