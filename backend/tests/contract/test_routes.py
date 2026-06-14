from travel_backend.main import app


def test_frozen_contract_routes_are_registered():
    routes = {(method, route.path) for route in app.routes for method in route.methods or []}
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
        ("GET", "/api/v1/plans/{plan_id}"),
        ("POST", "/api/v1/plans/{plan_id}/accept"),
        ("POST", "/api/v1/plans/{plan_id}/reject"),
        ("POST", "/api/v1/plans/{plan_id}/modify"),
        ("GET", "/api/v1/plans/{plan_id}/map"),
        ("GET", "/api/v1/plans/{plan_id}/calendar"),
        ("GET", "/internal/groups/{group_id}/context"),
        ("POST", "/internal/flights/search"),
        ("POST", "/internal/hotels/search"),
        ("POST", "/internal/tours/search"),
        ("POST", "/internal/plans/validate"),
    }
    assert expected <= routes
