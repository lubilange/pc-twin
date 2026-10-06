# pc-twin : surveillance ML 100 % locale d'un portable

## Problème
Les PC ne signalent un souci que via des seuils fixes, sans tenir compte du contexte.

## Solution
Un agent local collecte CPU, RAM, batterie, SSD et processus. Un Isolation Forest
apprend le comportement normal. Une API FastAPI locale (127.0.0.1) signale les
écarts et désigne le processus le plus actif.

## Architecture
Agent (psutil) -> SQLite -> features -> Isolation Forest (MLflow) -> API FastAPI

## Résultats (4 incidents provoqués : 2 CPU, 2 disque)
| | Rappel CPU | Rappel disque |
|---|---|---|
| Modèle (Isolation Forest) | 0 % | 100 % |
| Règle simple (CPU > 80 %) | 100 % | 0 % |

## Limites
- 2 incidents par type : chiffres indicatifs.
- Détection d'anomalies, pas prédiction de panne.
- Le mode hybride (modèle OU règle) a été identifié après coup : à valider sur de nouveaux incidents.
- Entraîné sur environ 13 h de données d'un seul PC.

## Lancer
pip install psutil pandas scikit-learn mlflow joblib fastapi uvicorn
python agent/collect.py        # en PowerShell administrateur (température SSD)
python training/train.py
python training/evaluate.py
uvicorn api.main:app --host 127.0.0.1 --port 8000

## Confidentialité
Les données (data/) et les modèles (models/) ne sont pas publiés : tout reste local.

## Suite
2e série d'incidents, réentraînement automatique, batterie et SSD, données anonymisées multi-PC.