"""
Iteration 4: forgot-password with delivery-status fallback (Resend sandbox workaround).

Covers:
- POST /api/auth/forgot-password for admin1 (Resend owner) -> delivered=true, otp_plain=None
- POST /api/auth/forgot-password for admin2/member (Resend blocked) -> delivered=false, otp_plain stored
- Unknown email -> success shape, no db entry (no enumeration)
- GET /api/admin/pending-otps -> admin-only, only failed non-used non-expired OTPs, no otp_hash
- POST /api/auth/verify-otp with otp_plain from pending-otps
- End-to-end reset-password for a failed-delivery member
- POST /api/admin/otps/{email}/resend -> success and 404
- Regressions: brute-force 429, /admin/stats keys, /me, /public/events
- Wrong OTP -> 400; reset invalidates (used=true)
- Cleanup: reset admin passwords, delete test members, purge pending OTPs
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://google-auth-otp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN1 = {"email": "mchanakya64@gmail.com", "password": "Admin@123"}
ADMIN2 = {"email": "siddharthsharma2649@gmail.com", "password": "Admin@123"}

TEST_MEMBER_EMAIL = f"test-fp-member-{uuid.uuid4().hex[:6]}@example.com"
TEST_MEMBER_PASSWORD = "testpass123"
TEST_MEMBER_NEW_PASSWORD = "NewTest@456"

# module-scoped shared state
STATE = {
    "member_id": None,
    "member_otp": None,
    "admin1_cookies": None,
    "admin2_cookies": None,
}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return s, r


@pytest.fixture(scope="module")
def admin1_session():
    s, r = _login(ADMIN1["email"], ADMIN1["password"])
    assert r.status_code == 200, f"Admin1 login failed: {r.status_code} {r.text}"
    STATE["admin1_cookies"] = s.cookies
    return s


@pytest.fixture(scope="module")
def admin2_session():
    s, r = _login(ADMIN2["email"], ADMIN2["password"])
    assert r.status_code == 200, f"Admin2 login failed: {r.status_code} {r.text}"
    STATE["admin2_cookies"] = s.cookies
    return s


# ---------- 01. Basic auth / smoke ----------
def test_01_admins_can_login(admin1_session, admin2_session):
    r = admin1_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"

    r2 = admin2_session.get(f"{API}/auth/me", timeout=15)
    assert r2.status_code == 200
    assert r2.json()["user"]["role"] == "admin"


# ---------- 02. Create test member ----------
def test_02_create_test_member(admin1_session):
    r = admin1_session.post(
        f"{API}/members",
        json={
            "email": TEST_MEMBER_EMAIL,
            "name": "TEST FP Member",
            "password": TEST_MEMBER_PASSWORD,
            "instrument": "guitar",
        },
        timeout=20,
    )
    assert r.status_code == 200, f"member create failed: {r.status_code} {r.text}"
    m = r.json()["member"]
    assert m["email"] == TEST_MEMBER_EMAIL
    assert m["role"] == "member"
    STATE["member_id"] = m["id"]


# ---------- 03. Forgot-password: admin1 (Resend owner) ----------
def test_03_forgot_password_admin1_delivered_true():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN1["email"]}, timeout=45)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    # NOTE: Only admin1 (Resend account owner) should deliver in sandbox mode.
    assert data.get("delivered") is True, (
        f"admin1 delivery expected true, got {data}. Resend key may be misconfigured."
    )


# ---------- 04. Forgot-password: admin2 (Resend blocks) — stores otp_plain ----------
def test_04_forgot_password_admin2_delivered_false():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN2["email"]}, timeout=45)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    assert data.get("delivered") is False, (
        f"admin2 delivery expected false (sandbox), got {data}."
    )


# ---------- 05. Forgot-password: test member (also blocked) ----------
def test_05_forgot_password_member_delivered_false():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": TEST_MEMBER_EMAIL}, timeout=45)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["delivered"] is False


# ---------- 06. Forgot-password: unknown email (no enumeration, no db entry) ----------
def test_06_forgot_password_unknown_email_no_db_entry(admin1_session):
    unknown = f"noone-{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/forgot-password", json={"email": unknown}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    # Should still return delivered=true (no leak: same happy shape)
    assert "delivered" in data

    # Verify no db entry via pending-otps (admin view)
    r2 = admin1_session.get(f"{API}/admin/pending-otps", timeout=15)
    assert r2.status_code == 200
    emails = [d.get("email") for d in r2.json().get("pending", [])]
    assert unknown not in emails, "Unknown email leaked into password_reset_otps"


# ---------- 07. GET /api/admin/pending-otps: auth required ----------
def test_07_pending_otps_requires_admin_auth():
    r = requests.get(f"{API}/admin/pending-otps", timeout=15)
    assert r.status_code == 401, f"expected 401, got {r.status_code} {r.text}"


def test_08_pending_otps_forbidden_for_member():
    # Login as freshly-created member (still original password)
    s, r = _login(TEST_MEMBER_EMAIL, TEST_MEMBER_PASSWORD)
    assert r.status_code == 200, f"member login failed: {r.text}"
    r2 = s.get(f"{API}/admin/pending-otps", timeout=15)
    assert r2.status_code == 403


# ---------- 09. GET /api/admin/pending-otps: shape + fetch OTP ----------
def test_09_pending_otps_returns_failed_only_with_plain(admin1_session):
    r = admin1_session.get(f"{API}/admin/pending-otps", timeout=15)
    assert r.status_code == 200
    pending = r.json().get("pending", [])
    assert isinstance(pending, list) and len(pending) >= 2, f"expected >=2, got {pending}"

    # Every entry must be delivery_status=failed, used=False, has otp_plain (6 digits), no otp_hash
    for entry in pending:
        assert entry.get("delivery_status") == "failed"
        assert entry.get("used") is False
        assert "otp_hash" not in entry, "otp_hash must NOT be exposed"
        otp = entry.get("otp_plain")
        assert isinstance(otp, str) and len(otp) == 6 and otp.isdigit(), f"bad otp_plain: {otp}"
        assert entry.get("delivery_error"), f"delivery_error should be set for failed: {entry}"
        for k in ("email", "user_name", "user_role", "expires_at", "created_at"):
            assert k in entry, f"missing field {k}"

    # Extract OTP for our test member
    match = [e for e in pending if e["email"] == TEST_MEMBER_EMAIL]
    assert len(match) == 1, f"member entry not found: {[e['email'] for e in pending]}"
    STATE["member_otp"] = match[0]["otp_plain"]

    # And admin2 entry should not have otp_hash either
    a2 = [e for e in pending if e["email"] == ADMIN2["email"]]
    assert len(a2) == 1
    assert a2[0].get("otp_plain") and len(a2[0]["otp_plain"]) == 6


# ---------- 10. Verify OTP with the plaintext from pending-otps ----------
def test_10_verify_otp_with_plaintext():
    assert STATE["member_otp"], "prev test must set member_otp"
    r = requests.post(
        f"{API}/auth/verify-otp",
        json={"email": TEST_MEMBER_EMAIL, "otp": STATE["member_otp"]},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


# ---------- 11. Wrong OTP -> 400 ----------
def test_11_verify_wrong_otp_400():
    r = requests.post(
        f"{API}/auth/verify-otp",
        json={"email": TEST_MEMBER_EMAIL, "otp": "000000"},
        timeout=15,
    )
    # Could be 400 (invalid) if wrong; but if the real OTP happens to be 000000, skip
    if STATE["member_otp"] == "000000":
        pytest.skip("Real OTP is 000000")
    assert r.status_code == 400, r.text


# ---------- 12. Reset-password happy path for failed-delivery member ----------
def test_12_reset_password_flow_member():
    assert STATE["member_otp"]
    r = requests.post(
        f"{API}/auth/reset-password",
        json={
            "email": TEST_MEMBER_EMAIL,
            "otp": STATE["member_otp"],
            "new_password": TEST_MEMBER_NEW_PASSWORD,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    # Old password should now fail
    _, r_old = _login(TEST_MEMBER_EMAIL, TEST_MEMBER_PASSWORD)
    assert r_old.status_code == 401

    # New password should succeed
    _, r_new = _login(TEST_MEMBER_EMAIL, TEST_MEMBER_NEW_PASSWORD)
    assert r_new.status_code == 200, r_new.text


# ---------- 13. OTP marked used after reset (cannot reuse) ----------
def test_13_otp_marked_used_after_reset():
    r = requests.post(
        f"{API}/auth/verify-otp",
        json={"email": TEST_MEMBER_EMAIL, "otp": STATE["member_otp"]},
        timeout=15,
    )
    assert r.status_code == 400
    assert "used" in r.text.lower() or "already" in r.text.lower()


# ---------- 14. Retry endpoint: 200 delivered=false for sandbox-blocked email ----------
def test_14_admin_resend_otp_still_failed(admin1_session):
    # admin2 pending OTP still valid (unused, not expired)
    r = admin1_session.post(f"{API}/admin/otps/{ADMIN2['email']}/resend", timeout=45)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    assert data.get("delivered") is False


def test_15_admin_resend_otp_404_when_no_pending(admin1_session):
    unknown = f"nopending-{uuid.uuid4().hex[:6]}@example.com"
    r = admin1_session.post(f"{API}/admin/otps/{unknown}/resend", timeout=15)
    assert r.status_code == 404


# ---------- 16. Regression: brute-force lockout still triggers at 5 fails ----------
def test_16_brute_force_lockout():
    # Use a unique email so we don't affect other users' state
    bogus = f"bruteforce-{uuid.uuid4().hex[:8]}@example.com"
    statuses = []
    for _ in range(6):
        r = requests.post(f"{API}/auth/login", json={"email": bogus, "password": "wrong"}, timeout=15)
        statuses.append(r.status_code)
    assert 429 in statuses, f"expected 429 after 5 fails, got {statuses}"


# ---------- 17. Regression: /admin/stats has required keys ----------
def test_17_admin_stats_shape(admin1_session):
    r = admin1_session.get(f"{API}/admin/stats", timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("rsvps", "waitlist", "sponsors"):
        assert k in d, f"missing key {k} in /admin/stats: {list(d.keys())}"


# ---------- 18. Regression: /public/events ----------
def test_18_public_events_ok():
    r = requests.get(f"{API}/public/events", timeout=20)
    assert r.status_code == 200
    assert "events" in r.json() or isinstance(r.json(), (list, dict))


# ---------- 19. Cleanup: delete test member, purge pending OTPs, reset admin pwds ----------
def test_19_cleanup(admin1_session):
    # Delete test member
    if STATE.get("member_id"):
        r = admin1_session.delete(f"{API}/members/{STATE['member_id']}", timeout=20)
        assert r.status_code in (200, 404), r.text

    # Reset admins by calling forgot-password + admin/pending-otps to fetch + reset back
    # ADMIN2: currently has pending OTP with delivery failed -> we can reset via that
    r = admin1_session.get(f"{API}/admin/pending-otps", timeout=15)
    assert r.status_code == 200
    pending = r.json().get("pending", [])

    # If admin2 has pending OTP, use it (unused/valid) — but we did NOT reset admin2 password during tests,
    # so admin2 already has Admin@123. Just purge its pending OTP by consuming with a reset to same pwd.
    a2 = [e for e in pending if e["email"] == ADMIN2["email"]]
    if a2:
        r2 = requests.post(
            f"{API}/auth/reset-password",
            json={"email": ADMIN2["email"], "otp": a2[0]["otp_plain"], "new_password": ADMIN2["password"]},
            timeout=20,
        )
        # ok even if it fails; primary goal is to have password back to Admin@123 (which it already is)
        assert r2.status_code in (200, 400)

    # Verify both admins can still log in with Admin@123
    _, ra1 = _login(ADMIN1["email"], ADMIN1["password"])
    assert ra1.status_code == 200, "admin1 login broken after tests"
    _, ra2 = _login(ADMIN2["email"], ADMIN2["password"])
    assert ra2.status_code == 200, "admin2 login broken after tests"
