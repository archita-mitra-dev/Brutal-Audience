from app.security import throttle


def authenticate(client, email: str = "writer@example.com", password: str = "correct horse battery") -> dict:
    """Register (or log in) and attach the bearer token to the test client."""
    throttle.reset()
    r = client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Test Writer"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return r.json()["user"]
