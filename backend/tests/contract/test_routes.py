from pathlib import Path

import yaml
from fastapi.routing import APIRoute

from travel_backend.main import app

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_frozen_contract_routes_are_registered():
    routes = {
        (method, route.path)
        for route in app.routes
        for method in route.methods or []
        if route.path.startswith("/api/v1") or route.path.startswith("/internal")
    }
    expected = {
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/chat"),
        ("POST", "/api/v1/chat/{run_id}/stream-ticket"),
        ("GET", "/api/v1/chat/{run_id}/stream"),
        ("POST", "/api/v1/chat/{run_id}/cancel"),
        ("GET", "/api/v1/sessions"),
        ("GET", "/api/v1/sessions/{session_id}"),
        ("GET", "/api/v1/groups"),
        ("POST", "/api/v1/groups"),
        ("GET", "/api/v1/groups/{group_id}"),
        ("GET", "/api/v1/groups/{group_id}/members"),
        ("GET", "/api/v1/groups/{group_id}/preferences"),
        ("GET", "/api/v1/groups/{group_id}/plans"),
        ("GET", "/api/v1/plans"),
        ("GET", "/api/v1/plans/{plan_id}"),
        ("POST", "/api/v1/plans/{plan_id}/accept"),
        ("POST", "/api/v1/plans/{plan_id}/reject"),
        ("POST", "/api/v1/plans/{plan_id}/modify"),
        ("GET", "/api/v1/plans/{plan_id}/map"),
        ("GET", "/api/v1/plans/{plan_id}/calendar"),
        ("GET", "/internal/groups/{group_id}/context"),
        ("POST", "/internal/groups/{group_id}/preferences"),
        ("POST", "/internal/flights/search"),
        ("POST", "/internal/hotels/search"),
        ("POST", "/internal/tours/search"),
        ("POST", "/internal/plans/validate"),
    }
    assert routes == expected


def test_registered_success_statuses_match_openapi_contracts():
    routes = {
        (method.lower(), route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or []
    }
    contracts = [
        (REPOSITORY_ROOT / "api" / "openapi.yaml", "/api/v1"),
        (
            REPOSITORY_ROOT / "agent-service" / "internal-tools-openapi.yaml",
            "/internal",
        ),
    ]
    for path, prefix in contracts:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for contract_path, path_item in document["paths"].items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                route = routes[(method, f"{prefix}{contract_path}")]
                success_statuses = sorted(
                    int(status) for status in operation["responses"] if str(status).startswith("2")
                )
                assert (route.status_code or 200) == success_statuses[0]


def test_frontend_map_point_extensions_are_additive_and_optional():
    frontend = yaml.safe_load(
        (REPOSITORY_ROOT / "api" / "openapi.yaml").read_text(encoding="utf-8")
    )
    agent = yaml.safe_load(
        (REPOSITORY_ROOT / "agent-service" / "openapi.yaml").read_text(encoding="utf-8")
    )
    frontend_map = frontend["components"]["schemas"]["MapPoint"]
    agent_map = agent["components"]["schemas"]["MapPoint"]
    core_fields = {"id", "name", "kind", "lat", "lng", "order"}

    assert set(frontend_map["required"]) == core_fields
    assert {"description", "summary", "food_recommendations", "signature_dishes"} <= set(
        frontend_map["properties"]
    )
    assert not (
        {"description", "summary", "food_recommendations", "signature_dishes"}
        & set(frontend_map["required"])
    )
    assert set(agent_map["required"]) == {"name", "kind", "lat", "lng", "order"}
    assert set(agent_map["properties"]) == {
        "name",
        "kind",
        "lat",
        "lng",
        "order",
        "note",
    }
