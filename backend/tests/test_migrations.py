import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from conftest import TEST_DB

BACKEND_DIR = Path(__file__).resolve().parents[1]


def migration_env(database: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
            "JWT_SECRET": "migration-test-secret-with-sufficient-length",
            "ACCESS_TOKEN_TTL_MINUTES": "15",
            "REFRESH_TOKEN_TTL_DAYS": "30",
            "BACKEND_TOOL_TOKEN": "migration-tool-token",
            "AGENT_SERVICE_URL": "http://agent.test",
            "AGENT_SERVICE_TOKEN": "migration-agent-token",
            "DEFAULT_LOCALE": "ru-RU",
            "SUPPORTED_LOCALES": "ru-RU,en-US",
            "CORS_ORIGINS": "http://localhost:5173",
            "LOG_LEVEL": "INFO",
        }
    )
    return env


def run_alembic(database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIR,
        env=migration_env(database),
        check=True,
        capture_output=True,
        text=True,
    )


def test_fresh_database_migrates_to_head(tmp_path):
    database = tmp_path / "fresh.db"
    run_alembic(database, "upgrade", "head")
    current = run_alembic(database, "current")
    assert "20260614_0003 (head)" in current.stdout
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()}
    assert "agent_message_id" in columns


def test_revision_0002_database_migrates_to_head(tmp_path):
    database = tmp_path / "revision-0002.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE messages (id VARCHAR PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        connection.execute("INSERT INTO alembic_version(version_num) VALUES ('20260614_0002')")
    run_alembic(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert "agent_message_id" in columns
    assert revision == "20260614_0003"


def test_startup_does_not_create_schema_without_migrations(tmp_path):
    database = tmp_path / "unmigrated.db"
    script = """
import asyncio
from asgi_lifespan import LifespanManager
from travel_backend.main import app

async def main():
    try:
        async with LifespanManager(app):
            pass
    except Exception:
        return
    raise RuntimeError("startup unexpectedly created the schema")

asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=migration_env(database),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "flight_offers" not in tables


def test_app_main_remains_the_supported_asgi_facade():
    from app.main import app as facade_app
    from travel_backend.main import app as implementation_app

    assert facade_app is implementation_app


def test_pytest_database_path_is_process_unique_and_outside_repository():
    assert str(os.getpid()) in TEST_DB.name
    assert TEST_DB.parent != BACKEND_DIR
