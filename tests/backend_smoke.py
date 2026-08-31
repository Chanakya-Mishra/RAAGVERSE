import os, sys, requests, uuid, time
from pymongo import MongoClient

BASE = "https://google-auth-otp.preview.emergentagent.com/api"
ADMIN1 = ("mchanakya64@gmail.com", "Admin@123")
ADMIN2 = ("siddharthsharma2649@gmail.com", "Admin@123")

results = {"passed": [], "failed": []}

def check(cond, name, detail=""):
    if cond:
        results["passed"].append(name)
        print(f"PASS: {name}")
    else:
        results["failed"].append(f"{name} :: {detail}")
        print(f"FAIL: {name} :: {detail}")

# 1. Health
r = requests.get(f"{BASE}/", timeout=15)
check(r.status_code == 200 and "online" in r.text, "GET /api/ health", f"{r.status_code} {r.text[:150]}")

# 2. Login admin1
s = requests.Session()
r = s.post(f"{BASE}/auth/login", json={"email": ADMIN1[0], "password": ADMIN1[1]}, timeout=15)
try:
    j = r.json()
except Exception:
    j = {}
check(r.status_code == 200 and j.get("user", {}).get("role") == "admin", "Admin1 login", f"{r.status_code} {r.text[:200]}")
check("access_token" in s.cookies and "refresh_token" in s.cookies, "Login sets cookies", f"cookies={list(s.cookies.keys())}")
access_token = j.get("access_token")

# 3. Login admin2
r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN2[0], "password": ADMIN2[1]}, timeout=15)
check(r.status_code == 200 and r.json().get("user", {}).get("role") == "admin", "Admin2 login", f"{r.status_code} {r.text[:150]}")

# 4. Wrong password 401
r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN1[0], "password": "wrong"}, timeout=15)
check(r.status_code == 401, "Wrong password 401", f"{r.status_code}")

# 5. /auth/me authenticated
r = s.get(f"{BASE}/auth/me", timeout=15)
check(r.status_code == 200 and r.json().get("user", {}).get("email") == ADMIN1[0], "auth/me authed", f"{r.status_code} {r.text[:150]}")

# 6. /auth/me unauth
r = requests.get(f"{BASE}/auth/me", timeout=15)
check(r.status_code == 401, "auth/me unauth 401", f"{r.status_code}")

# 7. Refresh
r2 = requests.Session()
r2.post(f"{BASE}/auth/login", json={"email": ADMIN1[0], "password": ADMIN1[1]}, timeout=15)
r = r2.post(f"{BASE}/auth/refresh", timeout=15)
check(r.status_code == 200 and "access_token" in r.json(), "auth/refresh", f"{r.status_code} {r.text[:150]}")

# 8. Forgot password + DB check
r = requests.post(f"{BASE}/auth/forgot-password", json={"email": ADMIN1[0]}, timeout=20)
check(r.status_code == 200 and r.json().get("success"), "forgot-password success", f"{r.status_code} {r.text[:150]}")

# Non-existent email - same response (no enum)
r = requests.post(f"{BASE}/auth/forgot-password", json={"email": "nobody-xyz@example.com"}, timeout=20)
check(r.status_code == 200 and r.json().get("success"), "forgot-password no enum", f"{r.status_code} {r.text[:150]}")

# 9. DB check - OTP record + indexes
mc = MongoClient("mongodb://localhost:27017")
db = mc["music_club_db"]
otp_rec = db.password_reset_otps.find_one({"email": ADMIN1[0]})
check(otp_rec is not None and "otp_hash" in otp_rec, "OTP record created with hash", str(otp_rec)[:200] if otp_rec else "None")

# Indexes
u_idx = list(db.users.index_information().keys())
o_idx = list(db.password_reset_otps.index_information().keys())
check(any("email" in k for k in u_idx), "users.email index", str(u_idx))
check(any("email" in k for k in o_idx), "password_reset_otps.email index", str(o_idx))

# 10. verify-otp with wrong OTP
r = requests.post(f"{BASE}/auth/verify-otp", json={"email": ADMIN1[0], "otp": "000000"}, timeout=15)
check(r.status_code == 400, "verify-otp wrong OTP -> 400", f"{r.status_code} {r.text[:150]}")

# 11. change-password wrong old
r = s.post(f"{BASE}/auth/change-password", json={"old_password": "wrongpass", "new_password": "NewPass@123"}, timeout=15)
check(r.status_code == 400, "change-password wrong old -> 400", f"{r.status_code} {r.text[:150]}")

# 12. Members list (admin)
r = s.get(f"{BASE}/members", timeout=15)
check(r.status_code == 200 and "members" in r.json(), "GET /members admin", f"{r.status_code}")

# 13. Members list unauth -> 401
r = requests.get(f"{BASE}/members", timeout=15)
check(r.status_code == 401, "GET /members unauth 401", f"{r.status_code}")

# 14. Create member
test_email = f"testmember_{uuid.uuid4().hex[:8]}@example.com"
r = s.post(f"{BASE}/members", json={"email": test_email, "name": "Test M", "password": "Passw0rd!", "instrument": "Guitar"}, timeout=15)
check(r.status_code == 200 and r.json().get("member", {}).get("email") == test_email, "Create member", f"{r.status_code} {r.text[:200]}")
member_id = r.json().get("member", {}).get("id") if r.status_code == 200 else None

# member has hashed password in DB
if member_id:
    dbm = db.users.find_one({"id": member_id})
    check(dbm and dbm.get("password_hash") and dbm["password_hash"] != "Passw0rd!", "Member password hashed", "")

# 15. Non-admin login and 403 on admin routes
if member_id:
    ns = requests.Session()
    r = ns.post(f"{BASE}/auth/login", json={"email": test_email, "password": "Passw0rd!"}, timeout=15)
    check(r.status_code == 200, "Non-admin login", f"{r.status_code}")
    r = ns.get(f"{BASE}/members", timeout=15)
    check(r.status_code == 403, "Non-admin /members -> 403", f"{r.status_code}")
    r = ns.get(f"{BASE}/admin/stats", timeout=15)
    check(r.status_code == 403, "Non-admin /admin/stats -> 403", f"{r.status_code}")

# 16. Cannot delete admin
admin_user = db.users.find_one({"email": ADMIN1[0]})
if admin_user:
    r = s.delete(f"{BASE}/members/{admin_user['id']}", timeout=15)
    check(r.status_code == 403, "Cannot delete admin", f"{r.status_code} {r.text[:150]}")

# 17. Delete created member
if member_id:
    r = s.delete(f"{BASE}/members/{member_id}", timeout=15)
    check(r.status_code == 200, "Delete member", f"{r.status_code}")

# 18. Events CRUD
r = s.post(f"{BASE}/events", json={"title": "Test Ev", "description": "d", "event_type": "Jam", "date": "2026-01-01T00:00:00", "location": "X", "capacity": 10, "published": True}, timeout=15)
check(r.status_code == 200, "Create event", f"{r.status_code} {r.text[:200]}")
ev_id = r.json().get("item", {}).get("id") if r.status_code == 200 else None
r = requests.get(f"{BASE}/public/events", timeout=15)
check(r.status_code == 200 and "events" in r.json(), "Public events", f"{r.status_code}")
if ev_id:
    r = s.put(f"{BASE}/events/{ev_id}", json={"title": "Test Ev 2"}, timeout=15)
    check(r.status_code == 200, "Update event", f"{r.status_code}")
    r = s.delete(f"{BASE}/events/{ev_id}", timeout=15)
    check(r.status_code == 200, "Delete event", f"{r.status_code}")

# 19. Sessions public
r = requests.get(f"{BASE}/public/sessions", timeout=15)
check(r.status_code == 200 and "sessions" in r.json(), "Public sessions", f"{r.status_code}")

# 20. Gallery public
r = requests.get(f"{BASE}/public/gallery", timeout=15)
check(r.status_code == 200 and "gallery" in r.json(), "Public gallery", f"{r.status_code}")

# 21. Admin stats
r = s.get(f"{BASE}/admin/stats", timeout=15)
j = r.json() if r.status_code == 200 else {}
check(r.status_code == 200 and all(k in j for k in ["members","admins","events","sessions","gallery"]), "Admin stats", f"{r.status_code} {j}")

# 22. Logout
r = s.post(f"{BASE}/auth/logout", timeout=15)
check(r.status_code == 200, "Logout", f"{r.status_code}")

# 23. Brute force lockout (5 wrong attempts) with fresh identifier
# Use a unique email to avoid affecting admin accounts
lock_email = f"lockout_{uuid.uuid4().hex[:6]}@example.com"
codes = []
for i in range(7):
    r = requests.post(f"{BASE}/auth/login", json={"email": lock_email, "password": "wrong"}, timeout=15)
    codes.append(r.status_code)
check(429 in codes, "Brute force lockout -> 429", f"codes={codes}")

print("\n=== Summary ===")
print(f"Passed: {len(results['passed'])}")
print(f"Failed: {len(results['failed'])}")
for f in results["failed"]:
    print("  -", f)
