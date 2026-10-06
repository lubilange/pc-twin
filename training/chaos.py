import multiprocessing as mp
import os, sqlite3, time
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "health.db"
DURATION, REST = 300, 300     # secondes
PLAN = ["cpu", "disk", "cpu", "disk"]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def burn(stop):
    while time.time() < stop:
        sum(i * i for i in range(10000))


def cpu_incident(sec):
    stop = time.time() + sec
    procs = [mp.Process(target=burn, args=(stop,)) for _ in range(mp.cpu_count())]
    for p in procs: p.start()
    for p in procs: p.join()


def disk_incident(sec):
    path = ROOT / "data" / "stress.bin"
    block = os.urandom(64 * 1024 * 1024)
    stop = time.time() + sec
    while time.time() < stop:
        with open(path, "wb") as f:
            for _ in range(8):
                f.write(block); f.flush(); os.fsync(f.fileno())
    path.unlink(missing_ok=True)


def log_event(kind, start, end):
    con = sqlite3.connect(DB, timeout=30)
    con.execute("INSERT INTO events VALUES (?,?,?)", (start, end, kind))
    con.commit(); con.close()


if __name__ == "__main__":
    print("Ne touche pas au PC. Durée totale : environ 35 minutes.")
    for i, kind in enumerate(PLAN):
        print(f"Incident {i+1}/{len(PLAN)} : {kind}")
        start = now()
        (cpu_incident if kind == "cpu" else disk_incident)(DURATION)
        log_event(kind, start, now())
        if i < len(PLAN) - 1:
            print("Repos 5 min")
            time.sleep(REST)
    print("Terminé.")