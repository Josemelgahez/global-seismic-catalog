import os
import time
import subprocess
import datetime

DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "seismic_catalog")

BACKUP_DIR = "/backups"
INTERVAL = int(os.getenv("BACKUP_INTERVAL_SECONDS", 86400))
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", 7))

def log(msg):
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def wait_for_db():
    while subprocess.call(["pg_isready", "-h", DB_HOST, "-U", DB_USER]) != 0:
        time.sleep(2)

def run_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M")
    backup_file = f"{BACKUP_DIR}/{DB_NAME}_backup_{timestamp}.sql"
    env = {**os.environ, "PGPASSWORD": DB_PASS}

    try:
        with open(backup_file, "w") as f:
            result = subprocess.run(
                ["pg_dumpall", "-h", DB_HOST, "-U", DB_USER],
                stdout=f,
                stderr=subprocess.PIPE,
                env=env
            )

        if result.returncode == 0:
            print(f"[✓] Backup completed successfully: {backup_file}")
        else:
            error_log = result.stderr.decode()
            print(f"[X] Backup failed: {error_log}")

    except Exception as e:
        print(f"[X] Exception during backup: {e}")

def cleanup_old_backups():
    now = time.time()
    for f in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, f)
        if os.path.isfile(path) and f.endswith(".sql"):
            age_days = (now - os.path.getmtime(path)) / 86400
            if age_days > RETENTION_DAYS:
                os.remove(path)

if __name__ == "__main__":
    wait_for_db()
    while True:
        run_backup()
        cleanup_old_backups()
        time.sleep(INTERVAL)