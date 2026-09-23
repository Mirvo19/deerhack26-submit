from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request

from ..githubsvc import reachable, refresh
from ..limits import limiter
from ..utils import csv_list, deadline_for, http_ok, gh_split, locked, md_safe

bp = Blueprint("submit", __name__)

field_keys = ("title", "tagline", "description", "github_url", "demo_url", "tech_stack", "members", "problem_statement")
pres_keys = ("presentation_type", "presentation_link")


def _fl():
    return locked(deadline_for(g.db, "fields_deadline"))


def _pl():
    return locked(deadline_for(g.db, "presentation_deadline"))


def _room(code):
    r = g.db.room_by_code(code or "")
    return (r, None, None) if r else (None, render_template("errors/404.html"), 404)


def _lst(sub, k):
    v = sub.get(k) or "[]"
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except Exception:
        return []


def _ctx(room):
    sub = g.db.ensure_submission(room["id"])
    cache = None
    if gh_split(sub.get("github_url") or ""):
        try:
            cache = refresh(g.db, sub, current_app.config["GITHUB_CACHE_TTL_MIN"])
        except Exception:
            cache = g.db.get_cache(sub["id"])
    return {
        "room": room,
        "sub": sub,
        "tech": _lst(sub, "tech_stack"),
        "members": _lst(sub, "members"),
        "cache": cache,
        "fl": _fl(),
        "pl": _pl(),
        "fdl": deadline_for(g.db, "fields_deadline"),
        "pdl": deadline_for(g.db, "presentation_deadline"),
    }


def _form():
    f = request.form
    return {
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
    }


def _vf(d, final):
    e = []
    if final and not d.get("title"):
        e.append("title needed for final.")
    if d.get("github_url"):
        if not gh_split(d["github_url"]):
            e.append("github url must be https://github.com/owner/repo.")
    elif final:
        e.append("github repo needed for final.")
    if d.get("demo_url") and not http_ok(d["demo_url"]):
        e.append("demo url must be a full http(s) url.")
    return e


def _vp(d):
    if d.get("presentation_type") == "link" and d.get("presentation_link") and not http_ok(d["presentation_link"]):
        return ["deck link must be a full http(s) url."]
    return []


def _is_fetch():
    return request.is_json or request.headers.get("X-Requested-With") == "fetch"


@bp.get("/submit/<team_code>")
@limiter.limit("30 per minute")
def editor(team_code):
    room, t, c = _room(team_code)
    if t:
        return t, c
    return render_template("submit.html", **_ctx(room))


@bp.post("/submit/<team_code>/save")
@limiter.limit("60 per minute")
def save_draft(team_code):
    room, t, c = _room(team_code)
    if t:
        return t, c
    fl, pl, fetch = _fl(), _pl(), _is_fetch()
    if fl and pl:
        if fetch:
            return jsonify({"ok": False, "error": "locked."}), 403
        flash("both locks passed - read-only now.", "error")
        return redirect(f"/submit/{room['team_code']}")
    d = _form()
    saved = []
    if not fl:
        errs = _vf(d, False)
        if errs and not (request.form.get("autosave") or fetch):
            for e in errs:
                flash(e, "error")
            return redirect(f"/submit/{room['team_code']}")
        d["description_html"] = md_safe(d["description"])
        saved.append("fields")
    else:
        for k in field_keys:
            d.pop(k, None)
    if not pl:
        errs = _vp(d)
        if errs and not fetch:
            for e in errs:
                flash(e, "error")
            return redirect(f"/submit/{room['team_code']}")
        if d.get("presentation_type") == "link":
            d["presentation_file"] = ""
        else:
            d["presentation_link"] = ""
        saved.append("presentation")
    else:
        for k in pres_keys:
            d.pop(k, None)
    d["status"] = "draft"
    g.db.save_submission(g.db.ensure_submission(room["id"])["id"], d)
    if fetch:
        return jsonify({"ok": True, "saved": saved, "saved_at": datetime.now(timezone.utc).isoformat()})
    flash(f"{' + '.join(saved)} saved.", "ok")
    return redirect(f"/submit/{room['team_code']}")


@bp.post("/submit/<team_code>/final")
@limiter.limit("20 per minute")
def submit_final(team_code):
    room, t, c = _room(team_code)
    if t:
        return t, c
    fl, pl = _fl(), _pl()
    if fl and pl:
        flash("both locks passed.", "error")
        return redirect(f"/submit/{room['team_code']}")
    sub = g.db.ensure_submission(room["id"])
    d = _form()
    src = dict(sub)
    fin = {"status": "final", "submitted_at": datetime.now(timezone.utc).isoformat()}
    if not fl:
        for k in field_keys:
            src[k] = fin[k] = d.get(k)
        src["description_html"] = fin["description_html"] = md_safe(d.get("description", ""))
    if not pl:
        for k in pres_keys:
            src[k] = fin[k] = d.get(k)
        if fin.get("presentation_type") == "link":
            src["presentation_file"] = fin["presentation_file"] = ""
        else:
            src["presentation_link"] = fin["presentation_link"] = ""
    errs = _vf(src, True) + _vp(src)
    if not errs and src.get("github_url"):
        ok, msg = reachable(src["github_url"])
        if not ok:
            errs.append(msg)
    if errs:
        for e in errs:
            flash(e, "error")
        return redirect(f"/submit/{room['team_code']}")
    g.db.save_submission(sub["id"], fin)
    try:
        refresh(g.db, {**sub, **fin}, 0, force=True)
    except Exception:
        pass
    flash("shipped. good luck - editable till each lock.", "ok")
    return redirect(f"/submit/{room['team_code']}")


@bp.post("/submit/<team_code>/shot")
def upload_shot(team_code):
    room, t, c = _room(team_code)
    if t:
        return jsonify({"ok": False}), c
    if _fl():
        return jsonify({"ok": False, "error": "locked"}), 403
    from ..storage import save_shot
    url, err = save_shot(current_app, request.files.get("shot"))
    if err:
        return jsonify({"ok": False, "error": err}), 400
    sub = g.db.ensure_submission(room["id"])
    g.db.save_submission(sub["id"], {"thumbnail_url": url})
    return jsonify({"ok": True, "url": url})


@bp.post("/submit/<team_code>/presentation/file")
@limiter.limit("20 per minute")
def pres_file(team_code):
    room, t, c = _room(team_code)
    if t:
        return jsonify({"ok": False}), c
    if _pl():
        return jsonify({"ok": False, "error": "locked"}), 403
    from ..storage import save_pres
    url, err = save_pres(current_app, request.files.get("file"))
    if err:
        return jsonify({"ok": False, "error": err}), 400
    sub = g.db.ensure_submission(room["id"])
    g.db.save_submission(sub["id"], {"presentation_type": "file", "presentation_file": url, "presentation_link": ""})
    return jsonify({"ok": True, "url": url})
