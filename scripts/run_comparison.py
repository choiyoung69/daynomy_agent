#!/usr/bin/env python3
"""Build an exact source copy, run isolated Spring/Rust servers, compare, then stop."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference/2026-DAYNOMY-dev/backend"
COPY = ROOT / ".local/spring-reference"
LOCAL = ROOT / ".local/comparison"
PG = Path("/opt/homebrew/opt/postgresql@18/bin")
DB_NAMES = ("daynomy_spring_compare_test", "daynomy_rust_compare_test")
PORTS = (18082, 18083)


def clean_env():
    # No inherited database/service settings, real API keys, JVM flags or profiles.
    return {"PATH": os.environ["PATH"], "LANG": "en_US.UTF-8", "TZ": "Asia/Seoul"}


def run(args, **kwargs):
    return subprocess.run(args, check=True, timeout=600, **kwargs)


def copy_source():
    COPY.mkdir(parents=True, exist_ok=True)
    files = [SOURCE / p for p in ("build.gradle.kts", "settings.gradle.kts", "gradlew")]
    files += list((SOURCE / "gradle").rglob("*")) + list((SOURCE / "src/main").rglob("*"))
    manifest = []
    for source in files:
        if not source.is_file():
            continue
        target = COPY / source.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({"path": str(source.relative_to(SOURCE)),
                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    expected = {entry["path"] for entry in manifest}
    copied = {str(p.relative_to(COPY))
              for folder in ("src/main", "gradle")
              for p in (COPY / folder).rglob("*") if p.is_file()}
    if copied - expected:
        raise RuntimeError("Stale files in source copy; inspect before rebuilding")
    (LOCAL / "source-snapshot.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify_source(manifest):
    for entry in manifest:
        for root in (SOURCE, COPY):
            if hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError("Original/source-copy hash changed")
    print(f"Original/source-copy hashes unchanged: {len(manifest)} files", flush=True)


def psql(database, sql):
    env = clean_env()
    env.update(PGHOST="127.0.0.1", PGPORT="55439", PGUSER="pilot", PGDATABASE=database,
               PGCONNECT_TIMEOUT="5")
    return run([str(PG / "psql"), "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1"],
               input=sql, text=True, capture_output=True, env=env).stdout.strip()


def spring_env(java_home):
    env = clean_env()
    env.update(
        JAVA_HOME=java_home, SPRING_CONFIG_IMPORT="", SPRING_PROFILES_ACTIVE="comparison",
        SPRING_CONFIG_ADDITIONAL_LOCATION=(LOCAL / "application-comparison.properties").as_uri(),
        DB_URL=f"jdbc:postgresql://127.0.0.1:55439/{DB_NAMES[0]}",
        DB_USERNAME="pilot", DB_PASSWORD="",
        GOOGLE_CLIENT_ID="local-comparison", GOOGLE_CLIENT_SECRET="local-comparison",
        JWT_SECRET=base64.b64encode(os.urandom(32)).decode(),
        AWS_REGION="ap-northeast-2", AWS_S3_BUCKET="local-comparison",
        AWS_S3_PUBLIC_BASE_URL="http://127.0.0.1:9",
        AWS_ACCESS_KEY_ID="local-comparison", AWS_SECRET_ACCESS_KEY="local-comparison",
        AWS_EC2_METADATA_DISABLED="true", PUBLIC_DATA_SERVICE_KEY="local-comparison",
        COOKIE_SECURE="false",
    )
    return env


def write_config():
    settings = {
        "server.address": "127.0.0.1", "server.port": str(PORTS[0]),
        "management.server.port": "-1",
        "management.otlp.metrics.export.enabled": "false",
        "management.tracing.export.otlp.enabled": "false",
        "spring.config.import": "",
        "spring.jpa.hibernate.ddl-auto": "validate",
        "spring.jpa.properties.hibernate.jdbc.time_zone": "Asia/Seoul",
        # All original migrations run only on the Spring comparison DB.
        "spring.flyway.enabled": "true",
    }
    for name in ("stock.us.sync", "stock.calendar.sync", "stock.sync", "stock.price.sync",
                 "exchange-rate.sync", "portfolio.snapshot", "league.calculation",
                 "investment-calendar.sync", "news.generation.korea", "news.generation.us",
                 "person.post-collection"):
        settings[name + ".enabled"] = "false"
    for name in ("external.krx-calendar.base-url", "external.openai.base-url",
                 "external.wikimedia.base-url", "external.youtube.base-url",
                 "external.eodhd.base-url", "external.public-data.stock-price-url",
                 "external.public-data.etf-price-url", "external.public-data.listed-stock-url",
                 "external.investment-calendar.bls-base-url",
                 "external.investment-calendar.bls-schedule-url",
                 "external.investment-calendar.bok-base-url",
                 "external.investment-calendar.ecos-base-url",
                 "external.investment-calendar.dart-base-url", "ai.openai.base-url",
                 "spring.security.oauth2.client.provider.google.authorization-uri",
                 "spring.security.oauth2.client.provider.google.token-uri",
                 "spring.security.oauth2.client.provider.google.user-info-uri",
                 "spring.security.oauth2.client.provider.google.jwk-set-uri"):
        settings[name] = "http://127.0.0.1:9"
    (LOCAL / "application-comparison.properties").write_text(
        "\n".join(f"{key}={value}" for key, value in settings.items()) + "\n"
    )


def start(command, env, cwd, label):
    with (LOCAL / f"{label}.log").open("w") as log:
        return subprocess.Popen(command, env=env, cwd=cwd, stdout=log, stderr=log)


def ready(process, port):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Server exited before ready; inspect local startup log")
        try:
            with opener.open(f"http://127.0.0.1:{port}/api/auth/csrf", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Server startup timeout")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError("Server required forced shutdown")
    if process.returncode not in (0, 143, -15):
        raise RuntimeError("Server exited abnormally")


def main():
    LOCAL.mkdir(parents=True, exist_ok=True)
    processes, manifest = [], None
    started_db = False
    code = 2
    try:
        run([sys.executable, "scripts/check.py", "preflight"], cwd=ROOT)
        run([sys.executable, "scripts/test_acceptance.py"], cwd=ROOT)
        run([sys.executable, "scripts/test_compare_feedback.py"], cwd=ROOT)
        java_home = subprocess.check_output(
            ["/usr/libexec/java_home", "-v", "21"], text=True).strip()
        manifest = copy_source()
        gradle_env = clean_env()
        gradle_env.update(JAVA_HOME=java_home, GRADLE_USER_HOME=str(ROOT / ".local/gradle"))
        # Prefer an existing exact wrapper distribution; otherwise use the copied wrapper.
        installed = sorted((Path.home() / ".gradle/wrapper/dists/gradle-9.5.1-bin").glob(
            "*/gradle-9.5.1/bin/gradle"))
        gradle = [str(installed[0])] if installed else ["bash", "gradlew"]
        run(gradle + ["--no-daemon", "--console=plain", "bootJar"], cwd=COPY, env=gradle_env)
        cargo_env = clean_env()
        cargo_env["CARGO_HOME"] = str(ROOT / ".local/cargo")
        run(["cargo", "build", "--manifest-path", "app/Cargo.toml", "--locked"],
            cwd=ROOT, env=cargo_env)
        for port in PORTS:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        db_running = subprocess.run(
            [str(PG / "pg_ctl"), "-D", str(ROOT / ".local/pgdata"), "status"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        started_db = not db_running
        run(["bash", "scripts/local-db.sh", "start"], cwd=ROOT, env=clean_env())
        for name in DB_NAMES:
            if psql("postgres", f"SELECT 1 FROM pg_database WHERE datname='{name}';") != "1":
                psql("postgres", f"CREATE DATABASE {name};")
        if psql(DB_NAMES[1], "SELECT to_regclass('public.feedbacks') IS NOT NULL;") != "t":
            psql(DB_NAMES[1], (ROOT / "app/migrations/001_feedbacks.sql").read_text())
        write_config()
        jars = list((COPY / "build/libs").glob("*-SNAPSHOT.jar"))
        if len(jars) != 1:
            raise RuntimeError("Expected one Spring boot jar")
        spring = start([str(Path(java_home) / "bin/java"), "-jar", str(jars[0])],
                       spring_env(java_home), COPY, "spring")
        processes.append(spring)
        ready(spring, PORTS[0])
        print("Spring HTTP ready (original security filters and PostgreSQL)", flush=True)
        rust_env = clean_env()
        rust_env.update(DATABASE_URL=f"postgresql://pilot@127.0.0.1:55439/{DB_NAMES[1]}",
                        PORT=str(PORTS[1]))
        rust = start([str(ROOT / "app/target/debug/daynomy-feedback")], rust_env, ROOT, "rust")
        processes.append(rust)
        ready(rust, PORTS[1])
        env = clean_env()
        for label, port, database in zip(("SPRING", "RUST"), PORTS, DB_NAMES):
            env[f"COMPARE_{label}_BASE_URL"] = f"http://127.0.0.1:{port}"
            env[f"COMPARE_{label}_DB_URL"] = f"postgresql://pilot@127.0.0.1:55439/{database}"
        code = subprocess.run([sys.executable, "scripts/compare_feedback.py"],
                              cwd=ROOT, env=env, timeout=180).returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED local comparison: " + type(exc).__name__, flush=True)
    finally:
        for process in reversed(processes):
            try:
                stop(process)
            except RuntimeError:
                print("Server cleanup/exit check failed", flush=True)
                code = 2
        if started_db:
            try:
                run(["bash", "scripts/local-db.sh", "stop"], cwd=ROOT, env=clean_env())
            except subprocess.SubprocessError:
                print("Test DB cleanup failed", flush=True)
                code = 2
        if manifest:
            try:
                verify_source(manifest)
            except (OSError, RuntimeError):
                print("Source integrity check failed", flush=True)
                code = 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
