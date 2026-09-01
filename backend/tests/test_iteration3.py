"""Iteration 3 backend tests: waitlist overflow + auto-promotion, rehearsal reminders, sponsors CRUD, regressions."""
import os
import uuid
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://google-auth-otp.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN1 = ("mchanakya64@gmail.com", "Admin@123")
ADMIN2 = ("siddharthsharma2649@gmail.com", "Admin@123")


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
    return {"events": [], "members": [], "sponsors": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session, created_ids):
    yield
    for eid in created_ids["events"]:
        try:
            admin_session.delete(f"{BASE}/events/{eid}", timeout=15)
        except Exception:
            pass
    for mid in created_ids["members"]:
        try:
            admin_session.delete(f"{BASE}/members/{mid}", timeout=15)
        except Exception:
            pass
    for sid in created_ids["sponsors"]:
        try:
            admin_session.delete(f"{BASE}/sponsors/{sid}", timeout=15)
        except Exception:
            pass


def _mk_event(admin_session, created_ids, capacity=2, days_ahead=30, title_suffix=""):
    dt = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(microsecond=0).isoformat()
    r = admin_session.post(f"{BASE}/events", json={
        "title": f"TEST WL {title_suffix} {uuid.uuid4().hex[:6]}",
        "description": "waitlist test",
        "event_type": "Jam",
        "date": dt,
        "location": "Test Room",
        "capacity": capacity,
        "published": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    ev = r.json()["item"]
    created_ids["events"].append(ev["id"])
    return ev


def _mk_member(admin_session, created_ids):
    email = f"test_it3_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "MemberPass@123"
    r = admin_session.post(f"{BASE}/members", json={
        "email": email, "name": "It3 Member", "password": pwd, "instrument": "Guitar"
    }, timeout=15)
    assert r.status_code == 200, r.text
    m = r.json()["member"]
    created_ids["members"].append(m["id"])
    ms = requests.Session()
    lr = ms.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert lr.status_code == 200
    return {"data": m, "session": ms, "email": email, "password": pwd}


# ============ Waitlist Overflow ============
class TestWaitlistOverflow:
    def test_public_rsvp_overflow_waitlists(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=2)
        results = []
        for i in range(4):
            r = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
                "name": f"P{i}", "email": f"p{i}_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
            }, timeout=15)
            assert r.status_code == 200, f"idx {i}: {r.status_code} {r.text}"
            results.append(r.json()["rsvp"])
        assert results[0]["status"] == "confirmed"
        assert results[1]["status"] == "confirmed"
        assert results[2]["status"] == "waitlisted"
        assert results[2]["waitlist_position"] == 1
        assert results[3]["status"] == "waitlisted"
        assert results[3]["waitlist_position"] == 2

    def test_admin_rsvp_list_shape(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=2)
        # add 3 rsvps
        for i in range(3):
            requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
                "name": f"S{i}", "email": f"s{i}_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
            }, timeout=15)
        r = admin_session.get(f"{BASE}/events/{ev['id']}/rsvps", timeout=15)
        assert r.status_code == 200
        j = r.json()
        for k in ("confirmed", "waitlisted", "total_seats", "capacity", "waitlist_count"):
            assert k in j, f"missing key {k} in {list(j.keys())}"
        assert j["capacity"] == 2
        assert len(j["confirmed"]) == 2
        assert len(j["waitlisted"]) == 1
        assert j["waitlist_count"] == 1
        assert j["total_seats"] == 2

    def test_member_rsvp_waitlisted_when_full(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=1)
        # fill via public
        r0 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "Filler", "email": f"filler_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
        }, timeout=15)
        assert r0.status_code == 200 and r0.json()["rsvp"]["status"] == "confirmed"
        # member rsvp should be waitlisted
        m = _mk_member(admin_session, created_ids)
        r = m["session"].post(f"{BASE}/events/{ev['id']}/rsvp", timeout=15)
        assert r.status_code == 200, r.text
        rsvp = r.json()["rsvp"]
        assert rsvp["status"] == "waitlisted"
        assert rsvp.get("waitlist_position") == 1


# ============ Auto-promotion on cancel ============
class TestAutoPromote:
    def test_admin_delete_promotes_first_waitlisted(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=2)
        rsvp_ids = []
        for i in range(4):
            r = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
                "name": f"AP{i}", "email": f"ap{i}_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
            }, timeout=15)
            rsvp_ids.append(r.json()["rsvp"]["id"])
        # Delete first confirmed
        first_confirmed_id = rsvp_ids[0]
        r = admin_session.delete(f"{BASE}/events/{ev['id']}/rsvps/{first_confirmed_id}", timeout=15)
        assert r.status_code == 200
        # Re-list
        lst = admin_session.get(f"{BASE}/events/{ev['id']}/rsvps", timeout=15).json()
        assert len(lst["confirmed"]) == 2, lst
        assert len(lst["waitlisted"]) == 1
        assert lst["total_seats"] == 2
        # The 3rd rsvp (first on waitlist, id=rsvp_ids[2]) should now be confirmed
        confirmed_ids = {d["id"] for d in lst["confirmed"]}
        assert rsvp_ids[2] in confirmed_ids, f"Expected {rsvp_ids[2]} promoted; confirmed={confirmed_ids}"
        # The 4th one remains waitlisted
        assert lst["waitlisted"][0]["id"] == rsvp_ids[3]

    def test_member_cancel_triggers_promotion(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=1)
        m = _mk_member(admin_session, created_ids)
        # Member RSVPs first -> confirmed
        r1 = m["session"].post(f"{BASE}/events/{ev['id']}/rsvp", timeout=15)
        assert r1.json()["rsvp"]["status"] == "confirmed"
        # Public rsvp gets waitlisted
        pub_email = f"wl_{uuid.uuid4().hex[:6]}@example.com"
        r2 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "WL", "email": pub_email, "guests": 1
        }, timeout=15)
        assert r2.json()["rsvp"]["status"] == "waitlisted"
        # Member cancels
        rc = m["session"].delete(f"{BASE}/events/{ev['id']}/rsvp", timeout=15)
        assert rc.status_code == 200
        # Verify public got promoted
        lst = admin_session.get(f"{BASE}/events/{ev['id']}/rsvps", timeout=15).json()
        assert len(lst["confirmed"]) == 1
        assert lst["confirmed"][0]["email"] == pub_email
        assert lst["waitlist_count"] == 0

    def test_fifo_promotion_skips_too_large(self, admin_session, created_ids):
        """cap=2, confirmed with 2 guests, then waitlist a 3-guest and a 1-guest via public.
        Cancel confirmed → freed=2. The 3-guest cannot fit, should skip and 1-guest gets promoted."""
        ev = _mk_event(admin_session, created_ids, capacity=2)
        r_conf = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "Big", "email": f"big_{uuid.uuid4().hex[:6]}@example.com", "guests": 2
        }, timeout=15)
        assert r_conf.json()["rsvp"]["status"] == "confirmed"
        conf_id = r_conf.json()["rsvp"]["id"]
        # waitlist 3-guest (won't fit)
        r_wl1 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "TooBig", "email": f"toobig_{uuid.uuid4().hex[:6]}@example.com", "guests": 3
        }, timeout=15)
        assert r_wl1.json()["rsvp"]["status"] == "waitlisted"
        wl1_id = r_wl1.json()["rsvp"]["id"]
        # waitlist 1-guest
        r_wl2 = requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "Fit", "email": f"fit_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
        }, timeout=15)
        assert r_wl2.json()["rsvp"]["status"] == "waitlisted"
        wl2_id = r_wl2.json()["rsvp"]["id"]
        # Cancel the confirmed
        rd = admin_session.delete(f"{BASE}/events/{ev['id']}/rsvps/{conf_id}", timeout=15)
        assert rd.status_code == 200
        lst = admin_session.get(f"{BASE}/events/{ev['id']}/rsvps", timeout=15).json()
        confirmed_ids = {d["id"] for d in lst["confirmed"]}
        waitlisted_ids = {d["id"] for d in lst["waitlisted"]}
        # wl2 (1 guest) should be promoted; wl1 (3 guests) stays waitlisted
        assert wl2_id in confirmed_ids
        assert wl1_id in waitlisted_ids


# ============ /me/rsvps enrichment ============
class TestMeRsvps:
    def test_me_rsvps_includes_waitlist_position_and_event(self, admin_session, created_ids):
        ev = _mk_event(admin_session, created_ids, capacity=1)
        # Fill capacity with public rsvp
        requests.post(f"{BASE}/public/events/{ev['id']}/rsvp", json={
            "name": "F", "email": f"f_{uuid.uuid4().hex[:6]}@example.com", "guests": 1
        }, timeout=15)
        m = _mk_member(admin_session, created_ids)
        rm = m["session"].post(f"{BASE}/events/{ev['id']}/rsvp", timeout=15)
        assert rm.json()["rsvp"]["status"] == "waitlisted"
        r = m["session"].get(f"{BASE}/me/rsvps", timeout=15)
        assert r.status_code == 200
        rsvps = r.json()["rsvps"]
        mine = [x for x in rsvps if x["event_id"] == ev["id"]]
        assert len(mine) == 1
        assert mine[0]["status"] == "waitlisted"
        assert mine[0].get("waitlist_position") == 1
        assert mine[0].get("event") and mine[0]["event"]["id"] == ev["id"]


# ============ Reminders ============
class TestReminders:
    def test_send_reminders_flow(self, admin_session, created_ids):
        # Create an event 24h from now with a member RSVP
        dt = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0).isoformat()
        r = admin_session.post(f"{BASE}/events", json={
            "title": f"TEST Reminder {uuid.uuid4().hex[:6]}",
            "description": "reminder test",
            "event_type": "Jam",
            "date": dt,
            "location": "Room R",
            "capacity": 10,
            "published": True,
        }, timeout=15)
        assert r.status_code == 200, r.text
        ev = r.json()["item"]
        created_ids["events"].append(ev["id"])
        m = _mk_member(admin_session, created_ids)
        rr = m["session"].post(f"{BASE}/events/{ev['id']}/rsvp", timeout=15)
        assert rr.json()["rsvp"]["status"] == "confirmed"

        # Call reminder endpoint
        resp = admin_session.post(f"{BASE}/admin/send-reminders", timeout=60)
        assert resp.status_code == 200, resp.text
        j = resp.json()
        for k in ("events_checked", "reminders_sent", "window"):
            assert k in j
        assert j["reminders_sent"] >= 1

        # Idempotency — call again
        resp2 = admin_session.post(f"{BASE}/admin/send-reminders", timeout=60)
        assert resp2.status_code == 200
        # Should not re-send to same rsvp — but other rsvps could have been created in parallel.
        # Filter: verify our rsvp is not re-sent by ensuring reminders_sent for our event is 0
        # We check via total: at minimum, the count should not include our specific rsvp again.
        # Best check: fetch admin rsvp list and verify reminder_sent_at exists on our rsvp
        lst = admin_session.get(f"{BASE}/events/{ev['id']}/rsvps", timeout=15).json()
        mine = [d for d in lst["rsvps"] if d.get("user_id") == m["data"]["id"]]
        assert mine and mine[0].get("reminder_sent_at")

    def test_send_reminders_requires_admin(self):
        r = requests.post(f"{BASE}/admin/send-reminders", timeout=15)
        assert r.status_code in (401, 403)


# ============ Sponsors ============
class TestSponsors:
    def test_public_sponsors_seed_and_sorted(self):
        r = requests.get(f"{BASE}/public/sponsors", timeout=15)
        assert r.status_code == 200
        sponsors = r.json()["sponsors"]
        assert isinstance(sponsors, list)
        assert all(s.get("active", True) for s in sponsors)
        names = [s["name"] for s in sponsors]
        for expected in ("Campus FM", "Riff & Roast", "Strings Bazaar"):
            assert expected in names, f"seed sponsor {expected} missing from {names}"
        # Sorted by order asc
        orders = [s.get("order", 100) for s in sponsors]
        assert orders == sorted(orders), f"not sorted by order: {orders}"

    def test_sponsors_crud(self, admin_session, created_ids):
        # CREATE
        payload = {
            "name": f"TEST Sponsor {uuid.uuid4().hex[:6]}",
            "tagline": "Test tagline",
            "website_url": "https://test.example.com",
            "logo_url": "",
            "tier": "Silver",
            "order": 5,
            "active": True,
        }
        r = admin_session.post(f"{BASE}/sponsors", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        item = r.json()["item"]
        sid = item["id"]
        created_ids["sponsors"].append(sid)
        assert item["name"] == payload["name"]
        assert item["tier"] == "Silver"

        # LIST (admin) shows it
        r_list = admin_session.get(f"{BASE}/sponsors", timeout=15)
        assert r_list.status_code == 200
        assert any(s["id"] == sid for s in r_list.json()["sponsors"])

        # Public shows it (active=true, low order → should appear early)
        rp = requests.get(f"{BASE}/public/sponsors", timeout=15)
        assert any(s["id"] == sid for s in rp.json()["sponsors"])

        # UPDATE
        r_upd = admin_session.put(f"{BASE}/sponsors/{sid}", json={"tagline": "Updated"}, timeout=15)
        assert r_upd.status_code == 200
        assert r_upd.json()["item"]["tagline"] == "Updated"

        # Set active=false → hidden from public
        r_hide = admin_session.put(f"{BASE}/sponsors/{sid}", json={"active": False}, timeout=15)
        assert r_hide.status_code == 200
        rp2 = requests.get(f"{BASE}/public/sponsors", timeout=15)
        assert not any(s["id"] == sid for s in rp2.json()["sponsors"])
        # But admin GET still returns it
        r_list2 = admin_session.get(f"{BASE}/sponsors", timeout=15)
        assert any(s["id"] == sid for s in r_list2.json()["sponsors"])

        # DELETE
        r_del = admin_session.delete(f"{BASE}/sponsors/{sid}", timeout=15)
        assert r_del.status_code == 200
        # Verify gone
        r_del2 = admin_session.delete(f"{BASE}/sponsors/{sid}", timeout=15)
        assert r_del2.status_code == 404
        created_ids["sponsors"].remove(sid)

    def test_sponsors_admin_only(self):
        r_get = requests.get(f"{BASE}/sponsors", timeout=15)
        assert r_get.status_code in (401, 403)
        r_post = requests.post(f"{BASE}/sponsors", json={"name": "x"}, timeout=15)
        assert r_post.status_code in (401, 403)


# ============ Regressions ============
class TestRegressions:
    def test_admin_stats_has_new_keys(self, admin_session):
        r = admin_session.get(f"{BASE}/admin/stats", timeout=15)
        assert r.status_code == 200
        j = r.json()
        for k in ("members", "admins", "events", "sessions", "gallery", "rsvps", "waitlist", "sponsors"):
            assert k in j, f"missing key {k}"

    def test_auth_me_after_login(self, admin_session):
        r = admin_session.get(f"{BASE}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == ADMIN1[0]

    def test_public_events_and_gallery(self):
        r = requests.get(f"{BASE}/public/events", timeout=15)
        assert r.status_code == 200 and "events" in r.json()
        r2 = requests.get(f"{BASE}/public/gallery", timeout=15)
        assert r2.status_code == 200 and "gallery" in r2.json()

    def test_forgot_password_sends_otp(self):
        r = requests.post(f"{BASE}/auth/forgot-password", json={"email": ADMIN2[0]}, timeout=20)
        # Should return 200 regardless (to prevent enumeration) or explicit success
        assert r.status_code == 200, r.text

    def test_brute_force_lockout(self):
        """5 failed attempts against a bogus email should trigger 429 lockout."""
        bogus_email = f"bogus_{uuid.uuid4().hex[:8]}@example.com"
        last_status = None
        for _ in range(6):
            r = requests.post(f"{BASE}/auth/login", json={"email": bogus_email, "password": "wrong"}, timeout=15)
            last_status = r.status_code
            if r.status_code == 429:
                break
        assert last_status == 429, f"Expected 429 lockout, got {last_status}"

    def test_members_list_still_works(self, admin_session):
        r = admin_session.get(f"{BASE}/members", timeout=15)
        assert r.status_code == 200
        assert "members" in r.json()
