"""Iteration 2 backend tests: gallery upload, member invite/bulk, RSVPs, google callback."""
import io
import os
import uuid
import csv
import struct
import zlib
import pytest
import requests

BASE = "https://google-auth-otp.preview.emergentagent.com/api"
ADMIN1 = ("mchanakya64@gmail.com", "Admin@123")
ADMIN2 = ("siddharthsharma2649@gmail.com", "Admin@123")


def _png_bytes(w=2, h=2):
    """Build a minimal valid PNG."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(typ, data):
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": ADMIN1[0], "password": ADMIN1[1]}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def created_ids():
    """Track resources for cleanup."""
    return {"members": [], "events": [], "gallery": [], "rsvps": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session, created_ids):
    yield
    # Cleanup members
    for mid in created_ids["members"]:
        try:
            admin_session.delete(f"{BASE}/members/{mid}", timeout=15)
        except Exception:
            pass
    for eid in created_ids["events"]:
        try:
            admin_session.delete(f"{BASE}/events/{eid}", timeout=15)
        except Exception:
            pass
    for gid in created_ids["gallery"]:
        try:
            admin_session.delete(f"{BASE}/gallery/{gid}", timeout=15)
        except Exception:
            pass


@pytest.fixture(scope="module")
def test_event(admin_session, created_ids):
    payload = {
        "title": "TEST RSVP Event",
        "description": "for rsvp tests",
        "event_type": "Jam",
        "date": "2026-06-01T18:00:00",
        "location": "Test Room",
        "capacity": 5,
        "published": True,
    }
    r = admin_session.post(f"{BASE}/events", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    ev = r.json()["item"]
    created_ids["events"].append(ev["id"])
    return ev


@pytest.fixture(scope="module")
def test_member(admin_session, created_ids):
    email = f"test_member_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "MemberPass@123"
    r = admin_session.post(f"{BASE}/members", json={
        "email": email, "name": "Test Member", "password": pwd, "instrument": "Guitar"
    }, timeout=15)
    assert r.status_code == 200, r.text
    m = r.json()["member"]
    created_ids["members"].append(m["id"])
    m["password"] = pwd
    # build a session for the member
    ms = requests.Session()
    lr = ms.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert lr.status_code == 200
    return {"data": m, "session": ms}


# ---------- Gallery Upload ----------
class TestGalleryUpload:
    def test_upload_png_success(self, admin_session, created_ids):
        png = _png_bytes()
        files = {"file": ("test.png", png, "image/png")}
        data = {"caption": "TEST gallery upload", "tag": "Jams", "photographer": "tester"}
        r = admin_session.post(f"{BASE}/gallery/upload", files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        item = r.json()["item"]
        assert item["caption"] == "TEST gallery upload"
        assert item["tag"] == "Jams"
        assert item["storage_path"].startswith(os.environ.get("APP_NAME", "music-club") + "/gallery/") or "/gallery/" in item["storage_path"]
        assert item["image_url"].startswith("/api/files/")
        created_ids["gallery"].append(item["id"])
        # Fetch via /api/files/{path}
        file_url = "https://google-auth-otp.preview.emergentagent.com" + item["image_url"]
        fr = requests.get(file_url, timeout=30)
        assert fr.status_code == 200
        assert fr.headers.get("Content-Type", "").startswith("image/")
        assert fr.content == png or len(fr.content) > 0

    def test_upload_rejects_non_image(self, admin_session):
        files = {"file": ("bad.txt", b"hello", "text/plain")}
        data = {"caption": "bad", "tag": "Jams"}
        r = admin_session.post(f"{BASE}/gallery/upload", files=files, data=data, timeout=30)
        assert r.status_code == 400

    def test_upload_rejects_oversize(self, admin_session):
        big = b"\x00" * (8 * 1024 * 1024 + 100)
        files = {"file": ("big.png", big, "image/png")}
        data = {"caption": "big", "tag": "Jams"}
        r = admin_session.post(f"{BASE}/gallery/upload", files=files, data=data, timeout=60)
        assert r.status_code == 400

    def test_upload_requires_admin(self):
        files = {"file": ("x.png", _png_bytes(), "image/png")}
        data = {"caption": "x", "tag": "Jams"}
        r = requests.post(f"{BASE}/gallery/upload", files=files, data=data, timeout=30)
        assert r.status_code in (401, 403)


# ---------- Member Invite ----------
class TestMemberInvite:
    def test_invite_creates_member(self, admin_session, created_ids):
        email = f"test_invite_{uuid.uuid4().hex[:8]}@example.com"
        r = admin_session.post(f"{BASE}/members/invite", json={
            "email": email, "name": "Invited One", "instrument": "Piano"
        }, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("invited") is True
        assert j["member"]["email"] == email
        assert "password_hash" not in j["member"]
        created_ids["members"].append(j["member"]["id"])

    def test_invite_duplicate_409(self, admin_session, created_ids):
        email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        r1 = admin_session.post(f"{BASE}/members/invite", json={"email": email, "name": "Dup"}, timeout=20)
        assert r1.status_code == 200
        created_ids["members"].append(r1.json()["member"]["id"])
        r2 = admin_session.post(f"{BASE}/members/invite", json={"email": email, "name": "Dup"}, timeout=20)
        assert r2.status_code == 409


# ---------- Bulk Import ----------
class TestBulkImport:
    def test_bulk_csv_creates(self, admin_session, created_ids):
        rows = [
            ["email", "name", "instrument"],
            [f"bulk_{uuid.uuid4().hex[:6]}@example.com", "Bulk A", "Guitar"],
            [f"bulk_{uuid.uuid4().hex[:6]}@example.com", "Bulk B", "Vocals"],
            [f"bulk_{uuid.uuid4().hex[:6]}@example.com", "Bulk C", ""],
        ]
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        content = buf.getvalue().encode()
        files = {"file": ("members.csv", content, "text/csv")}
        r = admin_session.post(f"{BASE}/members/bulk", files=files, data={"send_invite": "false"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["created"] == 3
        assert j["skipped_existing"] == 0
        assert isinstance(j["errors"], list)
        # cleanup: find and delete
        lr = admin_session.get(f"{BASE}/members", timeout=15)
        emails = {row[0] for row in rows[1:]}
        for m in lr.json()["members"]:
            if m["email"] in emails:
                created_ids["members"].append(m["id"])


# ---------- Public RSVP ----------
class TestPublicRsvp:
    def test_public_rsvp_success(self, test_event):
        email = f"guest_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE}/public/events/{test_event['id']}/rsvp", json={
            "name": "Guest One", "email": email, "guests": 1
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()["rsvp"]
        assert d["email"] == email
        assert d["guests"] == 1
        assert d["status"] == "confirmed"

    def test_public_rsvp_duplicate_email(self, test_event):
        email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
        r1 = requests.post(f"{BASE}/public/events/{test_event['id']}/rsvp", json={
            "name": "A", "email": email, "guests": 1
        }, timeout=15)
        assert r1.status_code == 200
        r2 = requests.post(f"{BASE}/public/events/{test_event['id']}/rsvp", json={
            "name": "A", "email": email, "guests": 1
        }, timeout=15)
        assert r2.status_code == 409

    def test_public_rsvp_capacity_full(self, admin_session, created_ids):
        # Create tiny event with capacity 2
        r = admin_session.post(f"{BASE}/events", json={
            "title": "TEST Full", "description": "d", "event_type": "Jam",
            "date": "2026-07-01T18:00:00", "location": "x", "capacity": 2, "published": True,
        }, timeout=15)
        ev = r.json()["item"]
        created_ids["events"].append(ev["id"])
        # Book 2 seats
        e1 = f"cap1_{uuid.uuid4().hex[:6]}@example.com"
        r1 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={"name": "A", "email": e1, "guests": 2}, timeout=15)
        assert r1.status_code == 200
        # Next one should fail
        e2 = f"cap2_{uuid.uuid4().hex[:6]}@example.com"
        r2 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={"name": "B", "email": e2, "guests": 1}, timeout=15)
        assert r2.status_code == 409

    def test_public_rsvp_count(self, test_event):
        r = requests.get(f"{BASE}/public/events/{test_event['id']}/rsvp-count", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json()["total"], int)
        assert r.json()["total"] >= 1


# ---------- Member RSVP ----------
class TestMemberRsvp:
    def test_member_rsvp_and_cancel(self, test_event, test_member):
        ms = test_member["session"]
        r = ms.post(f"{BASE}/events/{test_event['id']}/rsvp", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()["rsvp"]
        assert d["user_id"] == test_member["data"]["id"]
        # Duplicate
        r2 = ms.post(f"{BASE}/events/{test_event['id']}/rsvp", timeout=15)
        assert r2.status_code == 409
        # GET /me/rsvps
        r3 = ms.get(f"{BASE}/me/rsvps", timeout=15)
        assert r3.status_code == 200
        rsvps = r3.json()["rsvps"]
        assert any(x["event_id"] == test_event["id"] and x.get("event") for x in rsvps)
        # Cancel
        r4 = ms.delete(f"{BASE}/events/{test_event['id']}/rsvp", timeout=15)
        assert r4.status_code == 200
        # Cancel again 404
        r5 = ms.delete(f"{BASE}/events/{test_event['id']}/rsvp", timeout=15)
        assert r5.status_code == 404

    def test_member_rsvp_unauth(self, test_event):
        r = requests.post(f"{BASE}/events/{test_event['id']}/rsvp", timeout=15)
        assert r.status_code == 401


# ---------- Admin RSVPs list ----------
class TestAdminRsvps:
    def test_list_event_rsvps(self, admin_session, test_event):
        r = admin_session.get(f"{BASE}/events/{test_event['id']}/rsvps", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "rsvps" in j and "total_seats" in j
        assert isinstance(j["rsvps"], list)
        assert isinstance(j["total_seats"], int)

    def test_list_event_rsvps_forbidden_for_member(self, test_event, test_member):
        r = test_member["session"].get(f"{BASE}/events/{test_event['id']}/rsvps", timeout=15)
        assert r.status_code == 403


# ---------- Google Callback ----------
class TestGoogleCallback:
    def test_google_callback_invalid_session(self):
        r = requests.post(f"{BASE}/auth/google/callback", json={"session_id": "totally-fake-session-xyz"}, timeout=20)
        assert r.status_code == 401, f"expected 401 got {r.status_code} {r.text[:200]}"

    def test_google_callback_missing_body(self):
        r = requests.post(f"{BASE}/auth/google/callback", json={}, timeout=15)
        # Pydantic missing field -> 422
        assert r.status_code == 422


# ---------- Regression: Admin stats includes rsvps ----------
class TestRegression:
    def test_admin_stats_has_rsvps(self, admin_session):
        r = admin_session.get(f"{BASE}/admin/stats", timeout=15)
        assert r.status_code == 200
        j = r.json()
        for k in ("members", "admins", "events", "sessions", "gallery", "rsvps"):
            assert k in j, f"missing key {k}"

    def test_admin2_login(self):
        r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN2[0], "password": ADMIN2[1]}, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

    def test_public_gallery(self):
        r = requests.get(f"{BASE}/public/gallery", timeout=15)
        assert r.status_code == 200
        assert "gallery" in r.json()
