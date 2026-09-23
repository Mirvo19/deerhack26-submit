from __future__ import annotations

import uuid
from pathlib import Path

ext_ok = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
pres_ok = {".ppt", ".pptx"}


def _img_kind(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"GIF":
        return "gif"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _store(app, data, ext):
    from supabase import create_client
    name = uuid.uuid4().hex + ext
    try:
        create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_SERVICE_KEY"]).storage.from_(app.config["UPLOAD_BUCKET"]).upload(name, data)
        return f"/uploads/{name}", None
    except Exception as e:
        return None, f"storage broke: {e}"[:120]


def save_shot(app, f):
    if not f or not f.filename:
        return None, "no-file"
    ext = Path(f.filename).suffix.lower()
    if ext not in ext_ok:
        return None, "only png/jpg/webp/gif"
    data = f.read()
    if len(data) > app.config["MAX_UPLOAD_MB"] * 1024 * 1024:
        return None, f"too big (max {app.config['MAX_UPLOAD_MB']}mb)"
    if len(data) < 64 or _img_kind(data) not in ("png", "jpeg", "gif", "webp"):
        return None, "not a real image"
    return _store(app, data, ext)


def save_pres(app, f):
    if not f or not f.filename:
        return None, "no-file"
    ext = Path(f.filename).suffix.lower()
    if ext not in pres_ok:
        return None, "only ppt/pptx here - put anything else on drive and paste the link below"
    data = f.read()
    if len(data) > 50 * 1024 * 1024:
        return None, "too big (max 50mb) - put it on drive and paste the link below"
    if len(data) < 64:
        return None, "not a real file"
    head = data[:8]
    good = ((ext == ".pptx" and head[:2] == b"PK")
            or (ext == ".ppt" and head[:4] == b"\xd0\xcf\x11\xe0"))
    if not good:
        return None, "content does not match its type"
    return _store(app, data, ext)


def load_bytes(app, name):
    from supabase import create_client
    try:
        return create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_SERVICE_KEY"]).storage.from_(app.config["UPLOAD_BUCKET"]).download(Path(name).name)
    except Exception:
        return None
