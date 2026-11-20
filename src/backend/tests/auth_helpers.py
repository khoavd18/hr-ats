from fastapi.testclient import TestClient

PASSWORD = "synthetic-password-only"


def csrf_headers(client: TestClient) -> dict[str, str]:
    if "csrf_token" not in client.cookies:
        assert client.get("/api/v1/auth/csrf").status_code == 204
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def sign_in(client: TestClient, email="auth-user@example.invalid", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=csrf_headers(client),
    )
