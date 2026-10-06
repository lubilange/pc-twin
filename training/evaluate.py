import sqlite3
import pandas as pd, joblib, mlflow
from sklearn.metrics import precision_score, recall_score
from features import load_features, DB, ROOT

art = joblib.load(ROOT / "models" / "iforest.joblib")
df = load_features()
con = sqlite3.connect(DB)
ev = pd.read_sql("SELECT * FROM events", con, parse_dates=["start_ts", "end_ts"])
con.close()

df["label"], df["kind"] = 0, "normal"
for _, e in ev.iterrows():
    m = (df.ts >= e.start_ts) & (df.ts <= e.end_ts)
    df.loc[m, "label"], df.loc[m, "kind"] = 1, e.kind

pad = pd.Timedelta("10min")
test = df[(df.ts >= ev.start_ts.min() - pad) & (df.ts <= ev.end_ts.max() + pad)].copy()
test["pred_model"] = (art["model"].predict(test[art["features"]]) == -1).astype(int)
test["pred_rule"] = (test.cpu_pct > 80).astype(int)

print("Lignes de test :", len(test), "dont en incident :", int(test.label.sum()))
mlflow.set_experiment("pc-twin")
with mlflow.start_run(run_name="chaos-evaluation"):
    for name in ["model", "rule"]:
        p = precision_score(test.label, test[f"pred_{name}"], zero_division=0)
        r = recall_score(test.label, test[f"pred_{name}"], zero_division=0)
        print(f"{name:6s} précision {p:.2f} | rappel {r:.2f}")
        mlflow.log_metric(f"{name}_precision", p)
        mlflow.log_metric(f"{name}_recall", r)
    for kind in ["cpu", "disk"]:
        s = test[test.kind == kind]
        print(f"rappel {kind} (modèle) : {s.pred_model.mean():.2f}  | (règle) : {s.pred_rule.mean():.2f}")