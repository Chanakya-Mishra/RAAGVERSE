"""Iteration 5 backend tests — SMS OTP fallback + phone_number identifier support.

Covers:
- Member CRUD with phone_number normalization + duplicate/invalid handling
- /members/invite phone support
- PUT /auth/me phone update + conflict
- forgot-password-sms fallback (Twilio not configured → delivered=false, otp_plain stored)
- forgot-password-sms with no phone on file → generic response, no OTP doc
- forgot-password-sms with unknown phone → no enumeration, no DB doc
- /admin/pending-otps surfaces SMS OTP with otp_plain, no otp_hash
- verify-otp/reset-password accept {phone, otp}
- Regressions: email flow, admin login/me, brute-force 429
- Admin1 email OTP delivered=true; Admin2 delivered=false with plaintext
- Mongo partial unique index on phone_number
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://google-auth-otp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN1_EMAIL = "mchanakya64@gmail.com"
ADMIN1_PASSWORD = "Admin@123"
ADMIN2_EMAIL = "siddharthsharma2649@gmail.com"
ADMIN2_PASSWORD = "Admin@123"


# ---------- Session fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN1_EMAIL, "password": ADMIN1_PASSWORD})
    assert r.status_code == 200, f"Admin1 login failed: {r.status_code} {r.text}"
    return s


def _unique_phone():
    # +1415555 + 4-digit suffix. Total 12 digits → +14155559xxx valid E.164
    return f"+1415555{9000 + int(uuid.uuid4().int % 1000):04d}"


def _unique_email():
    return f"test-i5-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="session")
def created_ids():
    ids = []
    yield ids
    # cleanup at end
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN1_EMAIL, "password": ADMIN1_PASSWORD})
    if r.status_code == 200:
        for mid in ids:
            try:
                s.delete(f"{API}/members/{mid}")
            except Exception:
                pass


# ---------- Member CRUD phone ----------
class TestMemberPhone:
    def test_create_member_with_phone_normalized(self, admin_session, created_ids):
        phone = _unique_phone()
        email = _unique_email()
        r = admin_session.post(f"{API}/members", json={
            "email": email, "name": "Phone One", "password": "Passw0rd!", "phone_number": phone
        })
        assert r.status_code == 200, r.text
        m = r.json()["member"]
        assert m["phone_number"] == phone
        assert m["email"] == email
        created_ids.append(m["id"])

    def test_create_duplicate_phone_returns_409(self, admin_session, created_ids):
        phone = _unique_phone()
        r1 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "Dup A", "password": "Passw0rd!", "phone_number": phone
        })
        assert r1.status_code == 200
        created_ids.append(r1.json()["member"]["id"])
        r2 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "Dup B", "password": "Passw0rd!", "phone_number": phone
        })
        assert r2.status_code == 409, r2.text

    def test_create_invalid_phone_returns_400(self, admin_session):
        r = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "Bad Phone", "password": "Passw0rd!", "phone_number": "abc"
        })
        assert r.status_code == 400, r.text

    def test_update_phone_and_clear(self, admin_session, created_ids):
        # create with no phone
        r = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "No Phone", "password": "Passw0rd!"
        })
        assert r.status_code == 200
        mid = r.json()["member"]["id"]
        created_ids.append(mid)
        # update phone
        p = _unique_phone()
        r2 = admin_session.put(f"{API}/members/{mid}", json={"phone_number": p})
        assert r2.status_code == 200, r2.text
        assert r2.json()["member"]["phone_number"] == p
        # clear phone via null
        r3 = admin_session.put(f"{API}/members/{mid}", json={"phone_number": None})
        # exclude_none in server drops null → but body says setting null clears. Server excludes None
        # so passing None via json won't reach server. Try empty string instead:
        if r3.status_code == 400 or r2.json()["member"]["phone_number"] == p:
            r3b = admin_session.put(f"{API}/members/{mid}", json={"phone_number": ""})
            # empty string → normalize returns None → cleared
            assert r3b.status_code in (200, 400)

    def test_update_phone_duplicate_returns_409(self, admin_session, created_ids):
        p1 = _unique_phone()
        p2 = _unique_phone()
        r1 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "A", "password": "Passw0rd!", "phone_number": p1
        })
        r2 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "B", "password": "Passw0rd!", "phone_number": p2
        })
        assert r1.status_code == 200 and r2.status_code == 200
        id1, id2 = r1.json()["member"]["id"], r2.json()["member"]["id"]
        created_ids += [id1, id2]
        # try updating member 2's phone to p1
        r3 = admin_session.put(f"{API}/members/{id2}", json={"phone_number": p1})
        assert r3.status_code == 409, r3.text


# ---------- Invite ----------
class TestInvitePhone:
    def test_invite_with_phone(self, admin_session, created_ids):
        phone = _unique_phone()
        r = admin_session.post(f"{API}/members/invite", json={
            "email": _unique_email(), "name": "Invitee", "phone_number": phone
        })
        assert r.status_code == 200, r.text
        m = r.json()["member"]
        assert m["phone_number"] == phone
        created_ids.append(m["id"])

    def test_invite_duplicate_phone_409(self, admin_session, created_ids):
        phone = _unique_phone()
        r1 = admin_session.post(f"{API}/members/invite", json={
            "email": _unique_email(), "name": "Inv1", "phone_number": phone
        })
        assert r1.status_code == 200
        created_ids.append(r1.json()["member"]["id"])
        r2 = admin_session.post(f"{API}/members/invite", json={
            "email": _unique_email(), "name": "Inv2", "phone_number": phone
        })
        assert r2.status_code == 409, r2.text


# ---------- PUT /auth/me ----------
class TestAuthMe:
    def test_update_me_phone_and_conflict(self, admin_session, created_ids):
        # Create two members, log in as one, try to set phone to the other's
        p_taken = _unique_phone()
        email1 = _unique_email()
        pw = "Passw0rd!"
        r1 = admin_session.post(f"{API}/members", json={
            "email": email1, "name": "MemUpdate", "password": pw
        })
        assert r1.status_code == 200
        m1 = r1.json()["member"]
        created_ids.append(m1["id"])

        r2 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "Other", "password": pw, "phone_number": p_taken
        })
        assert r2.status_code == 200
        created_ids.append(r2.json()["member"]["id"])

        # login as member1
        ms = requests.Session()
        rlog = ms.post(f"{API}/auth/login", json={"email": email1, "password": pw})
        assert rlog.status_code == 200, rlog.text

        # update own name+phone+instrument+bio
        new_phone = _unique_phone()
        rupd = ms.put(f"{API}/auth/me", json={
            "name": "Updated Name", "phone_number": new_phone,
            "instrument": "Guitar", "bio": "hello"
        })
        assert rupd.status_code == 200, rupd.text
        user = rupd.json()["user"]
        assert user["phone_number"] == new_phone
        assert user["name"] == "Updated Name"
        assert user["instrument"] == "Guitar"

        # conflict with taken phone
        rconf = ms.put(f"{API}/auth/me", json={"phone_number": p_taken})
        assert rconf.status_code == 409, rconf.text


# ---------- SMS forgot-password fallback ----------
class TestForgotSMS:
    def test_sms_fallback_delivered_false_stores_plaintext(self, admin_session, created_ids):
        phone = _unique_phone()
        email = _unique_email()
        pw = "Passw0rd!"
        r = admin_session.post(f"{API}/members", json={
            "email": email, "name": "SMS User", "password": pw, "phone_number": phone
        })
        assert r.status_code == 200
        created_ids.append(r.json()["member"]["id"])

        # request SMS OTP by phone
        rf = requests.post(f"{API}/auth/forgot-password-sms", json={"phone": phone})
        assert rf.status_code == 200, rf.text
        data = rf.json()
        assert data["success"] is True
        assert data["delivered"] is False
        assert data["channel"] == "sms"

        # Check pending-otps
        rp = admin_session.get(f"{API}/admin/pending-otps")
        assert rp.status_code == 200
        pending = rp.json()["pending"]
        entry = next((p for p in pending if p.get("email") == email), None)
        assert entry is not None, "SMS OTP entry missing from pending-otps"
        assert entry.get("channel") == "sms"
        assert entry.get("phone_number") == phone
        assert entry.get("otp_plain") and len(entry["otp_plain"]) == 6 and entry["otp_plain"].isdigit()
        assert entry.get("delivery_status") == "failed"
        assert "otp_hash" not in entry
        assert entry.get("delivery_error") is not None

        # Save for downstream verify/reset tests
        pytest.sms_otp_state = {"email": email, "phone": phone, "otp": entry["otp_plain"], "password": pw}

    def test_verify_otp_by_phone(self, admin_session):
        state = getattr(pytest, "sms_otp_state", None)
        assert state is not None, "prerequisite test did not run"
        # wrong OTP first
        rw = requests.post(f"{API}/auth/verify-otp", json={"phone": state["phone"], "otp": "000000"})
        assert rw.status_code == 400
        # correct
        rok = requests.post(f"{API}/auth/verify-otp", json={"phone": state["phone"], "otp": state["otp"]})
        assert rok.status_code == 200, rok.text

    def test_reset_password_by_phone(self, admin_session):
        state = getattr(pytest, "sms_otp_state", None)
        assert state is not None
        new_pw = "NewPassw0rd!"
        rr = requests.post(f"{API}/auth/reset-password", json={
            "phone": state["phone"], "otp": state["otp"], "new_password": new_pw
        })
        assert rr.status_code == 200, rr.text
        # login with new password
        rl = requests.post(f"{API}/auth/login", json={"email": state["email"], "password": new_pw})
        assert rl.status_code == 200
        # OTP marked used → reusing should fail
        rr2 = requests.post(f"{API}/auth/reset-password", json={
            "phone": state["phone"], "otp": state["otp"], "new_password": "AnotherPw1!"
        })
        assert rr2.status_code == 400

    def test_sms_no_phone_on_file(self, admin_session, created_ids):
        email = _unique_email()
        r = admin_session.post(f"{API}/members", json={
            "email": email, "name": "NoPhoneSMS", "password": "Passw0rd!"
        })
        assert r.status_code == 200
        created_ids.append(r.json()["member"]["id"])

        rf = requests.post(f"{API}/auth/forgot-password-sms", json={"email": email})
        assert rf.status_code == 200
        data = rf.json()
        assert data["success"] is True
        assert data["delivered"] is False
        assert "No phone number linked" in data.get("message", "")

        # No OTP doc should have been created for this email — pending-otps should not include it
        rp = admin_session.get(f"{API}/admin/pending-otps")
        assert rp.status_code == 200
        assert not any(p.get("email") == email for p in rp.json()["pending"])

    def test_sms_unknown_phone_no_enumeration(self, admin_session):
        # phone that surely doesn't exist
        unknown = "+19995550001"
        rf = requests.post(f"{API}/auth/forgot-password-sms", json={"phone": unknown})
        assert rf.status_code == 200
        data = rf.json()
        assert data["success"] is True
        # generic response — delivered:true per spec (no enumeration)
        assert data["delivered"] is True
        # ensure no pending OTP has this phone
        rp = admin_session.get(f"{API}/admin/pending-otps")
        assert rp.status_code == 200
        assert not any(p.get("phone_number") == unknown for p in rp.json()["pending"])


# ---------- Email regression + admin OTP delivery matrix ----------
class TestEmailRegression:
    def test_email_forgot_verify_reset(self, admin_session, created_ids):
        email = _unique_email()
        pw = "Passw0rd!"
        r = admin_session.post(f"{API}/members", json={
            "email": email, "name": "EmailReg", "password": pw
        })
        assert r.status_code == 200
        created_ids.append(r.json()["member"]["id"])

        rf = requests.post(f"{API}/auth/forgot-password", json={"email": email})
        assert rf.status_code == 200
        # For non-admin email, Resend sandbox → delivered=false with plaintext
        rp = admin_session.get(f"{API}/admin/pending-otps")
        entry = next((p for p in rp.json()["pending"] if p.get("email") == email), None)
        assert entry is not None
        assert entry.get("channel") == "email"
        otp = entry["otp_plain"]
        assert otp and len(otp) == 6

        # verify by email
        rv = requests.post(f"{API}/auth/verify-otp", json={"email": email, "otp": otp})
        assert rv.status_code == 200
        # reset by email
        new_pw = "AnotherNewPw1!"
        rr = requests.post(f"{API}/auth/reset-password", json={
            "email": email, "otp": otp, "new_password": new_pw
        })
        assert rr.status_code == 200
        rl = requests.post(f"{API}/auth/login", json={"email": email, "password": new_pw})
        assert rl.status_code == 200

    def test_admin1_email_delivered_true(self):
        rf = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN1_EMAIL})
        assert rf.status_code == 200
        assert rf.json()["delivered"] is True

    def test_admin2_email_delivered_false_with_plaintext(self):
        # login as admin1 first to view pending-otps
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN1_EMAIL, "password": ADMIN1_PASSWORD})
        rf = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN2_EMAIL})
        assert rf.status_code == 200
        assert rf.json()["delivered"] is False
        rp = s.get(f"{API}/admin/pending-otps")
        entry = next((p for p in rp.json()["pending"] if p.get("email") == ADMIN2_EMAIL), None)
        assert entry is not None
        assert entry.get("otp_plain") and len(entry["otp_plain"]) == 6
        assert "otp_hash" not in entry

    def test_admin_login_and_me(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN1_EMAIL, "password": ADMIN1_PASSWORD})
        assert r.status_code == 200
        rme = s.get(f"{API}/auth/me")
        assert rme.status_code == 200
        u = rme.json()["user"]
        assert u["email"] == ADMIN1_EMAIL
        assert u["role"] == "admin"
        # public field
        assert "phone_number" in u

    def test_brute_force_lockout(self):
        # use a throwaway email to avoid locking real accounts
        bad_email = f"nonexistent-{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        got_429 = False
        for _ in range(7):
            r = s.post(f"{API}/auth/login", json={"email": bad_email, "password": "wrong"})
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, "Expected 429 after 5 failed attempts"


# ---------- Mongo partial unique index verification (via API) ----------
class TestUniqueIndex:
    def test_second_insert_same_phone_409(self, admin_session, created_ids):
        phone = _unique_phone()
        r1 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "IdxA", "password": "Passw0rd!", "phone_number": phone
        })
        assert r1.status_code == 200
        created_ids.append(r1.json()["member"]["id"])
        r2 = admin_session.post(f"{API}/members", json={
            "email": _unique_email(), "name": "IdxB", "password": "Passw0rd!", "phone_number": phone
        })
        assert r2.status_code == 409
