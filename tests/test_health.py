# tests/test_health.py
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_admin_requires_key(client):
    r = client.post("/admin/email/send-test")  # no header
    assert r.status_code in (401, 403)

def test_admin_accepts_key(client):
    r = client.post("/admin/email/send-test", headers={"X-API-Key": "test-key"})
    # Background task returns immediately
    assert r.status_code in (200, 202)
    assert r.json().get("queued") is True
