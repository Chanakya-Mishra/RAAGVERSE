"""Focused retest for normalize_phone fix (iteration 6).

Verifies:
- Garbage phone strings ('abc', '---') are rejected with 400.
- Empty string / missing phone_number still creates member with phone_number=null.
- PUT /api/members/{id} rejects garbage phone with 400.
- PUT /api/auth/me rejects garbage phone with 400.
- Valid E.164 phone still normalizes and persists.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://google-auth-otp.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "mchanakya64@gmail.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        # Some implementations use "email" instead of "identifier"
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = _unwrap(r.json())
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def created_ids():
    ids = []
    yield ids
    # Cleanup
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code == 200:
        token = r.json().get("access_token") or r.json().get("token")
        if token:
            s.headers.update({"Authorization": f"Bearer {token}"})
        for mid in ids:
            try:
                s.delete(f"{BASE_URL}/api/members/{mid}")
            except Exception:
                pass


def _unwrap(data):
    if isinstance(data, dict) and "member" in data and isinstance(data["member"], dict):
        return data["member"]
    return data


def _member_payload(**overrides):
    p = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "name": "TEST Phone Validation",
        "password": "Test@1234",
        "role": "member",
    }
    p.update(overrides)
    return p


class TestPhoneGarbageRejection:
    def test_create_member_phone_abc_rejected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/members", json=_member_payload(phone_number="abc"))
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "Phone must be E.164" in r.text

    def test_create_member_phone_dashes_rejected(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/members", json=_member_payload(phone_number="---"))
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "Phone must be E.164" in r.text


class TestPhoneEmptyOrNull:
    def test_create_member_empty_phone_accepted(self, admin_session, created_ids):
        r = admin_session.post(f"{BASE_URL}/api/members", json=_member_payload(phone_number=""))
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        data = _unwrap(r.json())
        assert data.get("phone_number") in (None, "")
        if data.get("id"):
            created_ids.append(data["id"])

    def test_create_member_no_phone_field_accepted(self, admin_session, created_ids):
        payload = _member_payload()
        payload.pop("phone_number", None)
        r = admin_session.post(f"{BASE_URL}/api/members", json=payload)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        data = _unwrap(r.json())
        assert data.get("phone_number") is None
        if data.get("id"):
            created_ids.append(data["id"])


class TestPutRejection:
    def test_put_member_garbage_phone_rejected(self, admin_session, created_ids):
        # create a valid member first
        r = admin_session.post(f"{BASE_URL}/api/members", json=_member_payload())
        assert r.status_code == 200, r.text
        mid = _unwrap(r.json())["id"]
        created_ids.append(mid)

        r2 = admin_session.put(f"{BASE_URL}/api/members/{mid}", json={"phone_number": "abc"})
        assert r2.status_code == 400, f"expected 400, got {r2.status_code}: {r2.text}"
        assert "Phone must be E.164" in r2.text

    def test_put_auth_me_garbage_phone_rejected(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/auth/me", json={"phone_number": "xyz"})
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "Phone must be E.164" in r.text


class TestValidPhoneRegression:
    def test_create_member_valid_phone(self, admin_session, created_ids):
        import random
        phone = f"+1415555{random.randint(1000, 9999)}"
        r = admin_session.post(f"{BASE_URL}/api/members", json=_member_payload(phone_number=phone))
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        data = _unwrap(r.json())
        assert data.get("phone_number") == phone
        mid = data["id"]
        created_ids.append(mid)

        # Verify persistence via GET
        r2 = admin_session.get(f"{BASE_URL}/api/members/{mid}")
        if r2.status_code == 200:
            assert _unwrap(r2.json()).get("phone_number") == phone
