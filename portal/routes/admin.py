from __future__ import annotations

import csv
import io
import json
import uuid

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, Response, url_for,
)
from werkzeug.security import generate_password_hash

from ..auth import can_audit, can_export, can_moderate, can_rooms, can_settings, can_staff, require_roles
from ..db import roles
from ..utils import csv_list, deadline_for, f_npt, http_ok, md_safe, npt_to_utc

bp = Blueprint("admin", __name__)


def _uid():
    return g.staff["uid"]


@bp.get("/rooms")
@require_roles(*can_rooms)
def rooms():
    rooms = g.db.list_rooms()
    by = {s.get("room_id"): s.get("status") for s in g.db.list_submissions_full()}
    return render_template("admin/rooms.html", rooms=rooms, tracks=g.db.get_setting("tracks") or [],
                           fdl=deadline_for(g.db, "fields_deadline"), pdl=deadline_for(g.db, "presentation_deadline"), status_by_room=by)


@bp.post("/rooms/new")
@require_roles(*can_rooms)
def room_new():
    name = (request.form.get("name") or "").strip()[:120]
    track = (request.form.get("track") or "open").strip().lower()[:80]
    room_loc = (request.form.get("room") or "").strip().lower()[:80]
    if not name:
        flash("name needed.", "error")
        return redirect(url_for("admin.rooms"))
    room = g.db.create_room(name, track, room_loc)
    g.db.ensure_submission(room["id"])
    g.db.audit(_uid(), g.role, "roommade", name, {"track": track, "room": room_loc})
    flash(f"room live - code {room['team_code']}", "ok")
    return redirect(url_for("admin.rooms"))


@bp.post("/rooms/<rid>/edit")
@require_roles(*can_rooms)
def room_edit(rid):
    g.db.update_room(rid, (request.form.get("name") or "").strip()[:120], (request.form.get("track") or "open").strip().lower()[:80], (request.form.get("room") or "").strip().lower()[:80])
    g.db.audit(_uid(), g.role, "roomedit", rid, {})
    flash("room updated.", "ok")
    return redirect(url_for("admin.rooms"))


@bp.post("/rooms/<rid>/delete")
@require_roles(*can_rooms)
def room_delete(rid):
    g.db.delete_room(rid)
    g.db.audit(_uid(), g.role, "roomdead", rid, {})
    flash("room nuked.", "ok")
    return redirect(url_for("admin.rooms"))


@bp.post("/settings")
@require_roles(*can_settings)
def settings_save():
    tracks = csv_list(request.form.get("tracks") or "") or ["open"]
    out, errs = {}, []
    for form_key, db_key in (("fields_deadline", "fields_deadline"), ("pres_deadline", "presentation_deadline")):
        raw = (request.form.get(form_key) or "").strip()
        if raw:
            utc = npt_to_utc(raw)
            if not utc:
                errs.append(f"{form_key} must look like 2026-03-01t09:00 (npt).")
            else:
                out[db_key] = utc.isoformat()
    if errs:
        for e in errs:
            flash(e, "error")
        return redirect(url_for("admin.rooms"))
    g.db.set_setting("tracks", tracks)
    for k, v in out.items():
        g.db.set_setting(k, v)
    g.db.audit(_uid(), g.role, "settingssaved", "tracks/deadlines", {"tracks": tracks, **out})
    flash("settings saved.", "ok")
    return redirect(url_for("admin.rooms"))


@bp.get("/moderate/<sid>")
@require_roles(*can_moderate)
def moderate(sid):
    sub = g.db.submission_by_id(sid)
    if not sub:
        return render_template("errors/404.html"), 404
    for k in ("tech_stack", "members"):
        try:
            sub[k] = json.loads(sub.get(k) or "[]") if isinstance(sub.get(k), str) else (sub.get(k) or [])
        except Exception:
            sub[k] = []
    return render_template("admin/moderate.html", sub=sub, room=g.db.room_by_id(sub.get("room_id")) or {})


@bp.post("/moderate/<sid>")
@require_roles(*can_moderate)
def moderate_save(sid):
    if not g.db.submission_by_id(sid):
        return render_template("errors/404.html"), 404
    f = request.form
    d = {
        "title": (f.get("title") or "").strip()[:160],
        "tagline": (f.get("tagline") or "").strip()[:220],
        "description": (f.get("description") or "")[:60000],
        "github_url": (f.get("github_url") or "").strip()[:500],
        "demo_url": (f.get("demo_url") or "").strip()[:500],
        "presentation_type": "file" if f.get("presentation_type") == "file" else "link",
        "presentation_link": (f.get("presentation_link") or "").strip()[:1000],
        "tech_stack": csv_list(f.get("tech_stack") or ""),
        "members": csv_list(f.get("members") or ""),
        "problem_statement": (f.get("problem_statement") or "")[:8000],
        "status": "final" if f.get("status") == "final" else "draft",
    }
    if d["presentation_type"] == "link":
        if d["presentation_link"] and not http_ok(d["presentation_link"]):
            flash("deck link must be a full http(s) url.", "error")
            return redirect(url_for("staff.project_detail", sid=sid))
        d["presentation_file"] = ""
    else:
        d["presentation_link"] = ""
    d["description_html"] = md_safe(d["description"])
    g.db.save_submission(sid, d)
    g.db.audit(_uid(), g.role, "subedited", sid, {"fields": sorted(d)})
    flash("edited. logged.", "ok")
    return redirect(url_for("staff.project_detail", sid=sid))


@bp.get("/export.csv")
@require_roles(*can_export)
def export_csv():
    subs = g.db.list_submissions_full()
    bag = {}
    for s in g.db.all_scores():
        v = [x for x in (s.get("innovation"), s.get("execution"), s.get("impact"), s.get("presentation")) if x]
        bag.setdefault(s.get("submission_id"), []).append(sum(v) / len(v) if v else 0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "team", "room", "track", "title", "tagline", "status", "github", "demo",
        "pres_type", "pres", "stack", "crew", "avg", "n", "updated_npt",
    ])
    for c in subs:
        sc = bag.get(c.get("id"), [])
        w.writerow([
            c.get("room_name"),
            c.get("room", ""),
            c.get("room_track"),
            c.get("title"),
            c.get("tagline"),
            c.get("status"),
            c.get("github_url"),
            c.get("demo_url"),
            c.get("presentation_type"),
            c.get("presentation_file") or c.get("presentation_link"),
            c.get("tech_stack"),
            c.get("members"),
            round(sum(sc) / len(sc), 2) if sc else "",
            len(sc),
            f_npt(c.get("updated_at")),
        ])
    g.db.audit(_uid(), g.role, "exported", "csv", {"rows": len(subs)})
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=deerhack-results.csv"})


@bp.get("/accounts")
@require_roles(*can_staff)
def accounts():
    return render_template("admin/accounts.html", staff={t: g.db.list_staff(t) for t in roles})


@bp.post("/accounts/new")
@require_roles(*can_staff)
def account_new():
    role = (request.form.get("role") or "").strip()
    name = (request.form.get("name") or "").strip()[:120]
    email = (request.form.get("email") or "").strip().lower()
    pw = request.form.get("password") or ""
    if role not in roles or not name or "@" not in email or len(pw) < 10:
        flash("need role + name + email + pw (10+).", "error")
        return redirect(url_for("admin.accounts"))
    if g.db.email_taken(email):
        flash("that email already lives in one role table. one role per human.", "error")
        return redirect(url_for("admin.accounts"))
    uid = uuid.uuid4().hex
    if current_app.config["USE_SUPABASE"]:
        try:
            from supabase import create_client
            sb = create_client(current_app.config["SUPABASE_URL"], current_app.config["SUPABASE_SERVICE_KEY"])
            uid = getattr(sb.auth.admin.create_user({"email": email, "password": pw, "email_confirm": True}).user, "id", uid)
        except Exception as e:
            flash(f"auth broke: {e}"[:200], "error")
            return redirect(url_for("admin.accounts"))
        g.db.create_staff(role, uid, name, email, None, _uid())
    else:
        g.db.create_staff(role, uid, name, email, generate_password_hash(pw), _uid())
    g.db.audit(_uid(), g.role, "mademan", email, {"role": role})
    flash(f"{role} live for {email}.", "ok")
    return redirect(url_for("admin.accounts"))


@bp.post("/accounts/<role>/<uid>/toggle")
@require_roles(*can_staff)
def account_toggle(role, uid):
    if role not in roles:
        return redirect(url_for("admin.accounts"))
    row = g.db.find_staff_by_uid(uid) or {}
    g.db.set_staff_active(role, uid, not row.get("active"))
    g.db.audit(_uid(), g.role, "toggled", uid, {"role": role})
    return redirect(url_for("admin.accounts"))


@bp.post("/accounts/<role>/<uid>/delete")
@require_roles(*can_staff)
def account_delete(role, uid):
    if role not in roles:
        return redirect(url_for("admin.accounts"))
    if uid == _uid():
        flash("no self-delete, chief.", "error")
        return redirect(url_for("admin.accounts"))
    g.db.delete_staff(role, uid)
    if current_app.config["USE_SUPABASE"]:
        try:
            from supabase import create_client
            create_client(current_app.config["SUPABASE_URL"], current_app.config["SUPABASE_SERVICE_KEY"]).auth.admin.delete_user(uid)
        except Exception:
            pass
    g.db.audit(_uid(), g.role, "axed", uid, {"role": role})
    flash("gone.", "ok")
    return redirect(url_for("admin.accounts"))


@bp.get("/codes")
@require_roles(*can_rooms)
def codes():
    track = request.args.get("track") or ""
    rooms = g.db.list_rooms()
    if track:
        rooms = [r for r in rooms if (r.get("track") or "") == track]
    return render_template("admin/codes.html", rooms=rooms, tracks=g.db.get_setting("tracks") or [], track=track)


@bp.get("/audit")
@require_roles(*can_audit)
def audit():
    return render_template("admin/audit.html", logs=g.db.audit_list())
