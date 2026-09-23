from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, render_template, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from config import cfg
from .db import get_db
from .limits import limiter
from .utils import f_npt, f_nptlocal

root = Path(__file__).resolve().parent.parent


def _asset_v():
    try:
        import subprocess
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    try:
        latest = 0
        for p in (root / "static").rglob("*"):
            if p.is_file():
                latest = max(latest, p.stat().st_mtime)
        return str(int(latest)) if latest else "1"
    except Exception:
        return "1"


def _rel(v):
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        s = (datetime.now(timezone.utc) - dt).total_seconds()
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{int(s // 60)}m ago"
        if s < 86400:
            return f"{int(s // 3600)}h ago"
        return f"{int(s // 86400)}d ago"
    except Exception:
        return "—"


def create_app():
    app = Flask(__name__, static_folder=str(root / "static"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.from_object(cfg())
    app.config["USE_SUPABASE"] = bool(app.config["SUPABASE_URL"] and app.config["SUPABASE_SERVICE_KEY"])
    app.config["ASSET_V"] = _asset_v()
    limiter.init_app(app)
    app.jinja_env.filters["reltime"] = _rel
    app.jinja_env.filters["npt"] = f_npt
    app.jinja_env.filters["nptlocal"] = f_nptlocal

    @app.before_request
    def _inj():
        from .auth import current_staff
        g.db = get_db(app)
        g.staff = current_staff(g.db)
        g.role = g.staff["role"] if g.staff else None

    from .routes.admin import bp as admin_bp
    from .routes.public import bp as public_bp
    from .routes.staff import bp as staff_bp
    from .routes.staff import login_view
    from .routes.submit import bp as submit_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(submit_bp)
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(admin_bp, url_prefix="/staff/manage")
    app.add_url_rule(app.config["STAFF_LOGIN_PATH"], "staff_login", login_view, methods=["GET", "POST"])

    @app.get("/uploads/<path:name>")
    def _up(name):
        from .storage import load_bytes
        data = load_bytes(app, name)
        if not data:
            return render_template("errors/404.html"), 404
        import io
        ext = name.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}.get(ext, "application/octet-stream")
        return send_file(io.BytesIO(data), mimetype=mime, max_age=86400)

    @app.after_request
    def _cache(resp):
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.errorhandler(403)
    def _403(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def _429(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def _500(e):
        return render_template("errors/500.html"), 500

    @app.context_processor
    def _g():
        try:
            name = g.db.get_setting("event_name") if hasattr(g, "db") else "deerhack"
        except Exception:
            name = "deerhack"
        return {"event_name": name,
                "asset_v": app.config["ASSET_V"],
                "staff": getattr(g, "staff", None), "role": getattr(g, "role", None),
                "now_utc": datetime.now(timezone.utc)}

    return app
