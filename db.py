import os, sqlite3, hashlib, hmac, secrets, json, time
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = os.getenv("STUDENT_AGENT_DB", str(Path(__file__).parent / "data" / "student_agent.db"))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return salt, digest

def init_db():
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, student_id TEXT NOT NULL, display_name TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS students(student_id TEXT PRIMARY KEY, programme TEXT, fee_status TEXT, outstanding_amount INTEGER, scholarship_status TEXT, scholarship_note TEXT);
        CREATE TABLE IF NOT EXISTS tickets(ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, issue TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(memory_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, memory_text TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS approvals(request_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, requested_change TEXT NOT NULL, status TEXT NOT NULL, requested_by TEXT NOT NULL, reviewed_by TEXT, result TEXT, created_at TEXT NOT NULL, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS audit(audit_id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT, decision TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
        """)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed_users = [
                ("student001", "Demo@123", "student001", "Aarav Patel", "student"),
                ("student002", "Demo@123", "student002", "Diya Shah", "student"),
                ("admin001", "Admin@123", "admin001", "Admin Reviewer", "admin"),
            ]
            for username, password, sid, name, role in seed_users:
                salt, digest = _hash_password(password)
                conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", (username, salt, digest, sid, name, role))
            conn.executemany("INSERT INTO students VALUES(?,?,?,?,?,?)", [
                ("student001", "PGDM Big Data Analytics", "Partially paid", 25000, "Under review", "Documents received; review pending."),
                ("student002", "PGDM Marketing", "Paid", 0, "Approved", "Scholarship approved in the demo record."),
            ])

def authenticate(username, password):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return None
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), row["password_salt"].encode(), 200_000).hex()
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return {"username": row["username"], "student_id": row["student_id"], "display_name": row["display_name"], "role": row["role"]}

def get_student_profile(student_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
    return dict(row) if row else None

def get_fee_status(target_student_id, requester):
    if requester["role"] != "admin" and requester["student_id"] != target_student_id:
        add_audit(requester["username"], "get_fee_status", target_student_id, "blocked", "cross-student access denied")
        return {"allowed": False, "permission": "blocked: cross-student access", "message": "Access denied. You can only view your own fee record."}
    profile = get_student_profile(target_student_id)
    if not profile:
        return {"allowed": False, "permission": "allowed but record missing", "message": "I couldn't find a fee record for that student ID."}
    add_audit(requester["username"], "get_fee_status", target_student_id, "allowed", "fee status read")
    return {"allowed": True, "permission": "allowed", "data": {"student_id": target_student_id, "fee_status": profile["fee_status"], "outstanding_amount_inr": profile["outstanding_amount"]}}

def get_scholarship_status(target_student_id, requester):
    if requester["role"] != "admin" and requester["student_id"] != target_student_id:
        add_audit(requester["username"], "get_scholarship_status", target_student_id, "blocked", "cross-student access denied")
        return {"allowed": False, "permission": "blocked: cross-student access", "message": "Access denied. You can only view your own scholarship record."}
    profile = get_student_profile(target_student_id)
    if not profile:
        return {"allowed": False, "permission": "allowed but record missing", "message": "I couldn't find a scholarship record for that student ID."}
    add_audit(requester["username"], "get_scholarship_status", target_student_id, "allowed", "scholarship status read")
    return {"allowed": True, "permission": "allowed", "data": {"student_id": target_student_id, "scholarship_status": profile["scholarship_status"], "note": profile["scholarship_note"]}}

def create_support_ticket(student, issue):
    safe_issue = issue[:500]
    with _connect() as conn:
        cur = conn.execute("INSERT INTO tickets(student_id,issue,status,created_at) VALUES(?,?,?,?)",
                           (student["student_id"], safe_issue, "Open", _now()))
        ticket_id = cur.lastrowid
    add_audit(student["username"], "create_support_ticket", f"ticket:{ticket_id}", "allowed", "ticket created")
    return {"allowed": True, "permission": "allowed", "message": f"Support ticket #{ticket_id} created with status Open."}

def request_sensitive_change(student, requested_change):
    if student["role"] != "student":
        return {"allowed": False, "permission": "blocked: student role required", "message": "Only a signed-in student can submit this change request."}
    with _connect() as conn:
        cur = conn.execute("INSERT INTO approvals(student_id,requested_change,status,requested_by,created_at) VALUES(?,?,?,?,?)",
                           (student["student_id"], requested_change[:500], "PENDING", student["username"], _now()))
        rid = cur.lastrowid
    return {"allowed": True, "permission": "allowed: staged for approval", "request_id": rid,
            "message": f"Your request #{rid} has been submitted for human approval. No student record has been changed yet."}

def get_pending_requests():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM approvals WHERE status='PENDING' ORDER BY request_id DESC").fetchall()
    return [dict(r) for r in rows]

def approve_change(request_id, reviewer):
    with _connect() as conn:
        item = conn.execute("SELECT * FROM approvals WHERE request_id=?", (request_id,)).fetchone()
        if not item or item["status"] != "PENDING":
            add_audit(reviewer, "approve_change", str(request_id), "blocked", "request missing or already reviewed")
            return False
        conn.execute("UPDATE approvals SET status='APPROVED', reviewed_by=?, result='Approved; demo approval recorded, no real institutional system connected', reviewed_at=? WHERE request_id=?",
                     (reviewer, _now(), request_id))
    add_audit(reviewer, "approve_change", str(request_id), "approved", "approval recorded; no external system modified")
    return True

def reject_change(request_id, reviewer):
    with _connect() as conn:
        item = conn.execute("SELECT * FROM approvals WHERE request_id=?", (request_id,)).fetchone()
        if not item or item["status"] != "PENDING":
            add_audit(reviewer, "reject_change", str(request_id), "blocked", "request missing or already reviewed")
            return False
        conn.execute("UPDATE approvals SET status='REJECTED', reviewed_by=?, result='Rejected; action not executed', reviewed_at=? WHERE request_id=?",
                     (reviewer, _now(), request_id))
    add_audit(reviewer, "reject_change", str(request_id), "rejected", "action not executed")
    return True

def save_memory(student_id, memory_text):
    with _connect() as conn:
        conn.execute("INSERT INTO memories(student_id,memory_text,created_at) VALUES(?,?,?)", (student_id, memory_text[:300], _now()))

def get_memories(student_id):
    with _connect() as conn:
        rows = conn.execute("SELECT memory_text,created_at FROM memories WHERE student_id=? ORDER BY memory_id DESC LIMIT 10", (student_id,)).fetchall()
    return [dict(r) for r in rows]

def add_audit(actor, action, target, decision, result):
    with _connect() as conn:
        conn.execute("INSERT INTO audit(actor,action,target,decision,result,created_at) VALUES(?,?,?,?,?,?)",
                     (actor, action, str(target)[:500], decision, str(result)[:500], _now()))

def get_recent_audit(limit=20):
    with _connect() as conn:
        rows = conn.execute("SELECT created_at,actor,action,target,decision,result FROM audit ORDER BY audit_id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
