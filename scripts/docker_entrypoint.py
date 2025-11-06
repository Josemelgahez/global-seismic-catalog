import os
import time
import subprocess
import sys

sys.path.append("/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_core.settings")

MODE = os.environ.get("ENTRYPOINT_MODE", "default").lower()

if MODE == "backup":
    print("[*] Starting in BACKUP mode.")
    host = os.environ.get("POSTGRES_HOST", "db")
    user = os.environ.get("POSTGRES_USER", "postgres")

    print("[*] Waiting for PostgreSQL to be ready...")
    while subprocess.call(["pg_isready", "-h", host, "-U", user]) != 0:
        time.sleep(2)
    print("[✓] PostgreSQL is ready! Starting automatic backups...")

    os.execvp("python", ["python", "/app/scripts/database_backup.py"])

else:
    import django
    from django.core.management import call_command

    env_export = "/etc/environment"
    env_vars = {
        k: v for k, v in os.environ.items()
        if any(p in k for p in ["POSTGRES_", "DJANGO_", "PYTHONUNBUFFERED"])
    }
    with open(env_export, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

    log_path = "/var/log/cron.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    open(log_path, "a").close()

    subprocess.run(["service", "cron", "start"], check=True)
    print("[✓] Cron service started.")

    print("[*] Waiting for PostgreSQL to be ready...")
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    while subprocess.call(["nc", "-z", host, port]) != 0:
        time.sleep(1)
    print("[✓] PostgreSQL up")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_core.settings")
    django.setup()

    print("[*] Checking for pending migrations...")
    subprocess.run(["python", "manage.py", "makemigrations", "--noinput"], check=False)

    print("[*] Applying migrations...")
    call_command("migrate", interactive=False)

    pg_conn = (
        f"PG:dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']} "
        f"host={os.environ['POSTGRES_HOST']}"
    )

    def table_exists(table_name):
        cmd = [
            "psql", "-h", host, "-U", os.environ["POSTGRES_USER"],
            "-d", os.environ["POSTGRES_DB"], "-tAc",
            f"SELECT to_regclass('{table_name}')"
        ]
        try:
            result = subprocess.check_output(
                cmd, text=True, env={**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
            ).strip()
            return result != ""
        except subprocess.CalledProcessError:
            return False

    if not table_exists("countries"):
        print("[*] Importing countries shapefile...")
        subprocess.run([
            "ogr2ogr", "-f", "PostgreSQL", pg_conn,
            "/app/api/static/countries_shp/ne_10m_admin_0_countries.shp",
            "-nln", "countries", "-nlt", "MULTIPOLYGON",
            "-lco", "GEOMETRY_NAME=geom", "-overwrite"
        ], check=True)

    if not table_exists("plates"):
        print("[*] Importing tectonic plates shapefile...")
        subprocess.run([
            "ogr2ogr", "-f", "PostgreSQL", pg_conn,
            "/app/api/static/PB2002_plates.json",
            "-nln", "plates", "-nlt", "MULTIPOLYGON",
            "-lco", "GEOMETRY_NAME=geom", "-overwrite"
        ], check=True)

    print("[✓] Geographic layers imported")

    print("[*] Starting Django server...")
    subprocess.Popen(["python", "manage.py", "runserver", "0.0.0.0:8000"])
    subprocess.run(["tail", "-F", log_path])