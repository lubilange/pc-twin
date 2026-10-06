import sqlite3
from pathlib import Path

con = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "health.db")
print("Mesures :", con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
print("\nDernières mesures :")
for r in con.execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT 3"):
    print(r)
print("\nDerniers processus :")
for r in con.execute("SELECT * FROM processes ORDER BY ts DESC LIMIT 10"):
    print(r)