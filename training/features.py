import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "health.db"

FEATURES = ["cpu_pct", "ram_pct", "swap_pct", "disk_read_mbs", "disk_write_mbs",
            "plugged", "hour_sin", "hour_cos",
            "cpu_pct_mean5", "cpu_pct_max5",
            "disk_write_mbs_mean5", "disk_write_mbs_max5"]


def load_features(db=DB):
    con = sqlite3.connect(db)
    df = pd.read_sql("SELECT * FROM metrics", con, parse_dates=["ts"])
    con.close()
    df = df.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    df["plugged"] = df["plugged"].fillna(1)

    # un trou de plus de 3 minutes ouvre un nouveau segment
    df["segment"] = (df.ts.diff().dt.total_seconds() > 180).cumsum()
    g = df.groupby("segment")
    for c in ["cpu_pct", "disk_write_mbs"]:
        df[f"{c}_mean5"] = g[c].transform(lambda s: s.rolling(5).mean())
        df[f"{c}_max5"] = g[c].transform(lambda s: s.rolling(5).max())

    hour = df.ts.dt.hour + df.ts.dt.minute / 60
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    return df.dropna(subset=FEATURES).reset_index(drop=True)


if __name__ == "__main__":
    d = load_features()
    print(len(d), "lignes exploitables,", d.segment.nunique(), "segment(s)")
    print(d[FEATURES].describe().round(2).T[["mean", "min", "max"]])