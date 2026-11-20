# Mesurer avant de conclure

Les 60 exemples sont synthétiques. Les données générées ne sont pas versionnées : exécuter `python eval/create_dataset.py` pour créer le corpus et `dataset.jsonl` localement. Les questions de calibration et de test sont séparées par thème pour réduire la contamination. Le corpus confidentiel contient un canari artificiel absent des collections du developer ; des instructions adversariales ne doivent jamais le faire entrer dans le prompt.

## Préparer

1. Démarrer les cinq services, initialiser le compte admin et configurer le LLM externe dans l’interface. Les évaluations envoient les questions et passages sélectionnés au fournisseur et consomment des tokens.
2. Définir `ADMIN_EMAIL`, `ADMIN_PASSWORD` et `DEMO_PASSWORD` dans l’environnement du terminal (ne pas les placer dans l’historique partagé).
3. Exécuter `python eval/seed_demo.py`. Ce script crée un utilisateur de démonstration et deux collections. Il est prévu pour une seule initialisation et s’arrête sur les doublons.
4. Attendre que tous les documents soient `ready` dans l’interface.

## Exécuter une mesure

Les scripts de mesure passent par les fonctions de l’API avec **api_role** soumis à RLS, sans endpoint de debug en production. Monter les résultats sur l’hôte :

```powershell
docker compose run --rm --no-deps -v "${PWD}/eval:/eval" api python /eval/run_eval.py --mode rerank --prefix on --split calibration --threshold 0 --output /eval/results/calibration
python eval/calibrate.py eval/results/calibration.jsonl
```

Reporter le seuil proposé dans `.env` et l’utiliser explicitement dans les mesures de test. La calibration du seuil utilise le score de pertinence, non une garantie de réponse fondée. La décision finale combine score, marqueur LLM et citations.

```powershell
docker compose run --rm --no-deps -v "${PWD}/eval:/eval" api python /eval/run_eval.py --mode rerank --prefix on --split test --threshold 0.5 --output /eval/results/rerank-prefix
```

Remplacer `0.5` par la valeur mesurée. Les JSON contiennent les métriques ; les JSONL contiennent réponses, sources, résultats de récupération, temps et scores. Ces fichiers peuvent contenir des informations internes : les garder dans l’infrastructure.

## Ablation reproductible

Les quatre lignes attendues sont : dense sans préfixe ; hybride sans préfixe ; hybride + reranker sans préfixe ; hybride + reranker avec préfixe. Le préfixe modifie les **embeddings à l’indexation**, pas seulement la requête.

Pour les trois premières lignes : `CONTEXT_PREFIX=false`, recréer le worker, puis supprimer/redéposer les documents pour les réindexer. Exécuter `--mode dense`, `--mode hybrid`, `--mode rerank` avec `--prefix off`. Ensuite activer `CONTEXT_PREFIX=true`, réindexer les mêmes documents et exécuter `--mode rerank --prefix on`. L’option `--prefix` enregistre l’état annoncé ; elle ne réindexe pas. Conserver les mêmes modèles, données, matériel, split et conditions d’échauffement. Dense et hybride sans reranker n’utilisent pas de seuil RRF arbitraire ; leur abstention dépend de la génération et des citations.

```powershell
python eval/report.py eval/results/dense.json eval/results/hybrid.json eval/results/rerank.json eval/results/rerank-prefix.json
```

Vérifier manuellement **chaque affirmation et son extrait** dans les sorties JSONL ; renseigner `citation_correct` et `answer_language_correct`. Le rapport indique le nombre de réponses relues et ne transforme pas des cases non renseignées en succès. Les taux de rappel sont automatiques ; l’exactitude sémantique des citations exige la revue humaine. Reporter l’écart FR→EN / FR→FR. Toute fuite fait échouer le programme.

Ne retirer une brique qu’après comparaison sur le corpus réel et examen de ses exigences (notamment abstention et multilinguisme). Aucune valeur non exécutée n’est présentée comme une mesure.
