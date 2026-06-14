import os
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

TEST_DB = Path(__file__).resolve().parents[1] / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret-with-sufficient-length"
os.environ["ACCESS_TOKEN_TTL_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_TTL_DAYS"] = "30"
os.environ["BACKEND_TOOL_TOKEN"] = "test-tool-token"
os.environ["AGENT_SERVICE_URL"] = "http://agent.test"
os.environ["AGENT_SERVICE_TOKEN"] = "test-agent-token"
os.environ["DEFAULT_LOCALE"] = "ru-RU"
os.environ["SUPPORTED_LOCALES"] = "ru-RU,en-US"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ["LOG_LEVEL"] = "INFO"

from travel_backend.database import Base, engine  # noqa: E402
from travel_backend.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def database():
    if TEST_DB.exists():
        TEST_DB.unlink()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with LifespanManager(app):
        yield
    await engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
async def client(database):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as http:
        yield http


@pytest.fixture
def unique_email():
    counter = getattr(unique_email, "counter", 0) + 1
    unique_email.counter = counter
    return f"user{counter}@example.com"


async def register_user(client: AsyncClient, email: str) -> tuple[dict, dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Тестовый пользователь", "email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data, {"Authorization": f"Bearer {data['tokens']['access_token']}"}


async def create_group(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/groups",
        headers=headers,
        json={
            "name": "Тестовая группа",
            "budget_rub": 180000,
            "origin_city": "Moscow",
            "destination": "IST",
            "start_date": "2026-07-10",
            "end_date": "2026-07-15",
            "members": [
                {
                    "full_name": "Иван Тестов",
                    "age": 35,
                    "preferences": [
                        {
                            "type": "meal",
                            "value": "breakfast",
                            "comment": "Нужен завтрак",
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def tool_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-tool-token",
        "X-Correlation-ID": "test-correlation",
    }
