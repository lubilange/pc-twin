import sqlite3
import pandas as pd, joblib
from sklearn.metrics import precision_score, recall_score
from features import load_features, DB, ROOT

art = joblib.load(ROOT / "models" / "iforest.joblib")
df = load_features()
con = sqlite3.connect(DB)
ev = pd.read_sql("SELECT * FROM events", con, parse_dates=["start_ts", "end_ts"])
con.close()

df["kind"] = "normal"
for _, e in ev.iterrows():
    m = (df.ts >= e.start_ts) & (df.ts <= e.end_ts)
    df.loc[m, "kind"] = e.kind
df["label"] = (df.kind != "normal").astype(int)
df["score"] = art["model"].decision_function(df[art["features"]])  # < 0 = anomalie

print("Scores du modèle par type (négatif = anomalie) :")
print(df.groupby("kind").score.agg(["count", "mean", "min", "max"]).round(3))

print("\nLignes des incidents CPU :")
cols = ["ts", "cpu_pct", "cpu_pct_mean5", "disk_write_mbs", "score"]
print(df[df.kind == "cpu"][cols].round(2).to_string(index=False))

pad = pd.Timedelta("10min")
t = df[(df.ts >= ev.start_ts.min() - pad) & (df.ts <= ev.end_ts.max() + pad)].copy()
t["model"] = (t.score < 0).astype(int)
t["rule"] = (t.cpu_pct > 80).astype(int)
t["hybride"] = t.model | t.rule
print()
for n in ["model", "rule", "hybride"]:
    print(f"{n:8s} précision {precision_score(t.label, t[n]):.2f} "
          f"| rappel {recall_score(t.label, t[n]):.2f}")