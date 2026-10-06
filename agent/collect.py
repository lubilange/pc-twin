import json, sqlite3, subprocess, time
import datetime as dt
from collections import defaultdict
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "health.db"
INTERVAL = 60          # secondes entre deux mesures
NCPU = psutil.cpu_count()
IGNORE = {"System Idle Process"}


def init_db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS metrics (
        ts TEXT, cpu_pct REAL, ram_pct REAL, swap_pct REAL,
        battery_pct REAL, plugged INT,
        disk_read_mbs REAL, disk_write_mbs REAL, disk_used_pct REAL,
        ssd_temp REAL, ssd_wear REAL);
    CREATE TABLE IF NOT EXISTS processes (
        ts TEXT, name TEXT, cpu_pct REAL, ram_mb REAL, kind TEXT);
    CREATE TABLE IF NOT EXISTS events (
        start_ts TEXT, end_ts TEXT, kind TEXT);
    """)
    con.commit()
    return con


def read_ssd():
    """Température et usure du SSD via PowerShell. Renvoie (None, None) en cas d'échec."""
    cmd = ("Get-PhysicalDisk | Get-StorageReliabilityCounter | "
           "Select-Object -First 1 Temperature, Wear | ConvertTo-Json")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                             capture_output=True, text=True, timeout=20).stdout
        d = json.loads(out)
        return d.get("Temperature"), d.get("Wear")
    except Exception:
        return None, None


def snapshot_processes():
    """CPU global + consommation par nom de processus sur ~1 seconde."""
    procs = []
    for p in psutil.process_iter(["name"]):
        try:
            p.cpu_percent(None)          # amorçage du compteur
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    psutil.cpu_percent(None)
    time.sleep(1)
    total_cpu = psutil.cpu_percent(None)

    agg = defaultdict(lambda: [0.0, 0.0])
    for p in procs:
        try:
            name = p.info["name"]
            if name in IGNORE:
                continue
            agg[name][0] += p.cpu_percent(None) / NCPU
            agg[name][1] += p.memory_info().rss / 1e6
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total_cpu, agg


def main():
    con = init_db()
    prev_io, prev_t = psutil.disk_io_counters(), time.time()
    temp = wear = None
    n = 0
    print(f"Agent démarré, une mesure toutes les {INTERVAL}s. Ctrl+C pour arrêter.")
    while True:
        t0 = time.time()
        if n % 5 == 0:
            temp, wear = read_ssd()
        cpu, agg = snapshot_processes()

        now = time.time()
        io = psutil.disk_io_counters()
        span = max(now - prev_t, 1)
        read_mbs = (io.read_bytes - prev_io.read_bytes) / 1e6 / span
        write_mbs = (io.write_bytes - prev_io.write_bytes) / 1e6 / span
        prev_io, prev_t = io, now

        bat = psutil.sensors_battery()
        bat_pct = bat.percent if bat else None
        plugged = int(bat.power_plugged) if bat else None
        ts = dt.datetime.now().isoformat(timespec="seconds")

        con.execute("INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, cpu, psutil.virtual_memory().percent,
                     psutil.swap_memory().percent, bat_pct, plugged,
                     read_mbs, write_mbs, psutil.disk_usage("C:\\").percent,
                     temp, wear))
        top_cpu = sorted(agg.items(), key=lambda x: x[1][0], reverse=True)[:5]
        top_ram = sorted(agg.items(), key=lambda x: x[1][1], reverse=True)[:5]
        for kind, top in (("cpu", top_cpu), ("ram", top_ram)):
            for name, (c, r) in top:
                con.execute("INSERT INTO processes VALUES (?,?,?,?,?)",
                            (ts, name, c, r, kind))
        con.commit()

        print(f"{ts} | CPU {cpu:.0f}% | RAM {psutil.virtual_memory().percent:.0f}% "
              f"| batterie {bat_pct}% | SSD {temp}°C")
        n += 1
        time.sleep(max(0, INTERVAL - (time.time() - t0)))


if __name__ == "__main__":
    main()