import sqlite3
import pandas as pd, joblib, mlflow
from sklearn.ensemble import IsolationForest
from features import load_features, FEATURES, DB, ROOT

df = load_features()

# si des tests de chaos existent, on s'arrête avant le premier
con = sqlite3.connect(DB)
ev = pd.read_sql("SELECT * FROM events", con, parse_dates=["start_ts", "end_ts"])
con.close()
if len(ev):
    df = df[df.ts < ev.start_ts.min() - pd.Timedelta("5min")]
print("Entraînement sur", len(df), "mesures normales")

params = {"n_estimators": 200, "contamination": 0.01, "random_state": 42}
mlflow.set_experiment("pc-twin")
with mlflow.start_run(run_name="isolation-forest"):
    model = IsolationForest(**params).fit(df[FEATURES])
    mlflow.log_params(params)
    mlflow.log_param("n_train", len(df))
    mlflow.log_metric("train_anomaly_rate", float((model.predict(df[FEATURES]) == -1).mean()))
    joblib.dump({"model": model, "features": FEATURES}, ROOT / "models" / "iforest.joblib")
print("Modèle sauvegardé dans models/iforest.joblib")