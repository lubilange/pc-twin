import sqlite3, sys
from pathlib import Path
import joblib, pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
from features import load_features, DB  # noqa: E402

app = FastAPI(title="pc-twin (local)")
MODEL_PATH = ROOT / "models" / "iforest.joblib"
state = {"art": joblib.load(MODEL_PATH)}


class Event(BaseModel):
    start_ts: str   # ex. "2026-10-07T14:00:00"
    end_ts: str
    kind: str       # "cpu", "disk", "ram", ...


@app.post("/reload")
def reload_model():
    state["art"] = joblib.load(MODEL_PATH)
    return {"status": "modèle rechargé"}


@app.get("/health")
def health(minutes: int = 10):
    df = load_features()
    if df.empty:
        return {"erreur": "Pas assez de mesures : lance agent/collect.py"}
    last = df.iloc[-1]
    art = state["art"]
    score = float(art["model"].decision_function(df[art["features"]].tail(1))[0])
    model_alert = score < 0
    rule_alert = bool(last.cpu_pct > 80)

    con = sqlite3.connect(DB)
    procs = pd.read_sql(
        "SELECT name, cpu_pct, ram_mb, kind FROM processes WHERE ts = "
        "(SELECT MAX(ts) FROM processes)", con)
    con.close()
    culprit = None
    if not procs.empty:
        top = procs[procs.kind == "cpu"].sort_values("cpu_pct", ascending=False)
        if not top.empty:
            culprit = {"processus": top.iloc[0]["name"],
                       "cpu_pct": round(float(top.iloc[0]["cpu_pct"]), 1)}

    alert = model_alert or rule_alert
    if alert and culprit:
        msg = (f"Comportement inhabituel détecté. Processus le plus actif : "
               f"{culprit['processus']} ({culprit['cpu_pct']} % CPU).")
    elif alert:
        msg = "Comportement inhabituel détecté."
    else:
        msg = "Comportement normal pour ce portable."

    return {"mesure": str(last.ts), "score_modele": round(score, 3),
            "alerte_modele": model_alert, "alerte_regle_cpu": rule_alert,
            "alerte": alert, "processus_principal": culprit, "message": msg,
            "note": "Détection d'anomalies, pas une prédiction de panne."}


@app.post("/events")
def add_event(e: Event):
    con = sqlite3.connect(DB, timeout=30)
    con.execute("INSERT INTO events VALUES (?,?,?)", (e.start_ts, e.end_ts, e.kind))
    con.commit(); con.close()
    return {"status": "incident enregistré"}


@app.get("/events")
def list_events():
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT start_ts, end_ts, kind FROM events").fetchall()
    con.close()
    return [{"start_ts": a, "end_ts": b, "kind": c} for a, b, c in rows]