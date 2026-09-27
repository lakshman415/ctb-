"""
Tests for the health check endpoint.

Verifies the app boots and responds correctly.
"""


def test_health_check(client):
    """GET /api/v1/health should return 200 with status=healthy."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
