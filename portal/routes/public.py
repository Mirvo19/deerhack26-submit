from __future__ import annotations

from flask import Blueprint, g, jsonify, redirect, render_template, request

from ..limits import limiter

bp = Blueprint("public", __name__)


@bp.get("/")
def landing():
    s = g.db.get_many("submission_deadline", "tracks")
    return render_template("landing.html", deadline=s["submission_deadline"],
                           tracks=s["tracks"] or [], error=request.args.get("error"))


@bp.post("/enter")
@limiter.limit("10 per minute")
def enter():
    code = (request.form.get("team_code") or "").strip().lower()
    if not code:
        return redirect("/?error=type+your+room+code")
    room = g.db.room_by_code(code)
    if not room:
        return redirect("/?error=code+not+found.+ask+your+organizer.")
    return redirect(f"/submit/{room['team_code']}")


@bp.get("/check/<team_code>")
@limiter.limit("10 per minute")
def check(team_code):
    room = g.db.room_by_code(team_code or "")
    if not room:
        return jsonify({"ok": False})
    return jsonify({"ok": True, "name": room.get("name", "")})
