from __future__ import annotations

from functools import wraps

from flask import abort, current_app, g, redirect, session

from .db import get_db

can_score = {"judge", "superadmin"}
can_rooms = {"admin", "superadmin"}
can_settings = {"admin", "superadmin"}
can_moderate = {"admin", "superadmin"}
can_export = {"admin", "superadmin"}
can_staff = {"superadmin"}
can_audit = {"superadmin"}
all_staff = {"judge", "mentor", "admin", "superadmin"}


def current_staff(db=None):
    uid = session.get("staff_uid")
    if not uid:
        return None
    row = (db or get_db()).find_staff_by_uid(uid)
    return row if row and row.get("active") else None


def login_staff(uid):
    session.clear()
    session["staff_uid"] = uid


def logout_staff():
    session.clear()


def require_roles(*rs):
    ok = set(rs)

    def deco(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            db = get_db(current_app)
            me = current_staff(db)
            if not me:
                return redirect(f"{current_app.config['STAFF_LOGIN_PATH']}?next={_nxt()}")
            if me["role"] not in ok:
                abort(403)
            g.staff, g.role = me, me["role"]
            return fn(*a, **kw)
        return wrap
    return deco


def _nxt():
    from flask import request
    n = request.path or "/"
    return n if n.startswith("/") and not n.startswith("//") else "/"
