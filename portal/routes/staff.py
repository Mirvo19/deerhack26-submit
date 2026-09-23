from __future__ import annotations

import json
import uuid

from flask import (
    Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for,
)
from werkzeug.security import check_password_hash

from ..auth import all_staff, can_score, current_staff, login_staff, logout_staff, require_roles
from ..githubsvc import refresh
from ..limits import limiter
from ..utils import score_n

bp = Blueprint("staff", __name__)


def _ok_pw(h, pw):
    try:
        return bool(h) and check_password_hash(h, pw or "")
    except Exception:
        return False


def _sb_signin(email, pw):
    url, key = current_app.config["SUPABASE_URL"], current_app.config["SUPABASE_SERVICE_KEY"]
    if not (url and key):
        return None
    try:
        from supabase import create_client
        r = create_client(url, key).auth.sign_in_with_password({"email": email, "password": pw})
        return getattr(getattr(r, "user", None), "id", None)
    except Exception:
        return None


@limiter.limit("10 per minute")
def login_view():
    db = g.db
    if request.method == "GET":
        return redirect(url_for("staff.home")) if current_staff(db) else render_template("staff/login.html", nxt=request.args.get("next", ""))
    email = (request.form.get("email") or "").strip().lower()
    row = db.find_staff_by_email(email)
    if not row:
        flash("bad login.", "error")
        return render_template("staff/login.html"), 401
    if not row.get("active"):
        flash("account off - ping a superadmin.", "error")
        return render_template("staff/login.html"), 403
    pw = request.form.get("password") or ""
    authed = bool(_sb_signin(email, pw)) if current_app.config["USE_SUPABASE"] else _ok_pw(row.get("password_hash"), pw)
    if not authed:
        flash("bad login.", "error")
        return render_template("staff/login.html"), 401
    login_staff(row["uid"])
    nxt = request.form.get("next") or url_for("staff.home")
    return redirect(nxt if nxt.startswith("/") else url_for("staff.home"))


@bp.get("/logout")
def logout():
    logout_staff()
    return redirect("/")


@bp.get("/")
@require_roles(*all_staff)
def home():
    return redirect(url_for({"judge": "staff.projects", "mentor": "staff.projects", "admin": "admin.rooms", "superadmin": "admin.rooms"}[g.role]))


@bp.get("/projects")
@require_roles(*all_staff)
def projects():
    cards = g.db.list_submissions_full()
    q = (request.args.get("q") or "").lower()
    track = request.args.get("track") or ""
    if q:
        cards = [c for c in cards if q in f"{c.get('title', '')} {c.get('tagline', '')} {c.get('room_name', '')}".lower()]
    if track:
        cards = [c for c in cards if (c.get("room_track") or "") == track]
    avg = {}
    if g.role in ("judge", "admin", "superadmin"):
        bag = {}
        for s in g.db.all_scores():
            v = [x for x in (s.get("innovation"), s.get("execution"), s.get("impact"), s.get("presentation")) if x]
            bag.setdefault(s.get("submission_id"), []).append(sum(v) / len(v) if v else 0)
        avg = {k: round(sum(v) / len(v), 1) for k, v in bag.items()}
    sort = request.args.get("sort") or "recent"
    if sort == "top" and avg:
        cards.sort(key=lambda c: (avg.get(c.get("id")) is None, -(avg.get(c.get("id")) or 0)))
    return render_template("staff/projects.html", cards=cards, tracks=g.db.get_setting("tracks") or [], q=request.args.get("q", ""), track=track, avgs=avg, sort=sort)


@bp.get("/projects/<sid>")
@require_roles(*all_staff)
def project_detail(sid):
    sub = g.db.submission_by_id(sid)
    if not sub:
        return render_template("errors/404.html"), 404
    for k in ("tech_stack", "members"):
        try:
            sub[k] = json.loads(sub.get(k) or "[]") if isinstance(sub.get(k), str) else (sub.get(k) or [])
        except Exception:
            sub[k] = []
    ss = g.db.scores_for(sid)
    per = []
    for s in ss:
        v = [x for x in (s.get("innovation"), s.get("execution"), s.get("impact"), s.get("presentation")) if x]
        if v:
            per.append(sum(v) / len(v))
    return render_template("staff/project_detail.html", sub=sub, room=g.db.room_by_id(sub["room_id"]) or {},
                           cache=g.db.get_cache(sid) or {}, scores=ss,
                           score_avg=round(sum(per) / len(per), 1) if per else None)


@bp.post("/projects/<sid>/score")
@require_roles(*can_score)
def score(sid):
    g.db.add_score(
        sid,
        g.staff["uid"],
        {k: score_n(request.form.get(k)) for k in ("innovation", "execution", "impact", "presentation")}
        | {"notes": (request.form.get("notes") or "")[:4000]},
    )
    g.db.audit(g.staff["uid"], g.role, "scoresaved", sid, {})
    flash("score stacked.", "ok")
    return redirect(url_for("staff.project_detail", sid=sid))


@bp.post("/projects/<sid>/refresh-github")
@require_roles(*all_staff)
def refresh_github(sid):
    sub = g.db.submission_by_id(sid)
    if not sub:
        return jsonify({"ok": False}), 404
    try:
        c = refresh(g.db, sub, current_app.config["GITHUB_CACHE_TTL_MIN"], force=True)
        return jsonify({"ok": True, "fetched_at": str((c or {}).get("fetched_at"))})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 502
