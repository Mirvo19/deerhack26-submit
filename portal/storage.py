from __future__ import annotations

import uuid
from pathlib import Path

ext_ok = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
pres_ok = {".pdf", ".ppt", ".pptx", ".key", ".zip", ".mp4", ".mov", ".webm"}


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
    name = uuid.uuid4().hex + ext
    url, key = app.config["SUPABASE_URL"], app.config["SUPABASE_SERVICE_KEY"]
    if url and key:
        try:
            from supabase import create_client
            create_client(url, key).storage.from_(app.config["UPLOAD_BUCKET"]).upload(name, data)
            return f"/uploads/{name}", None
        except Exception as e:
            return None, f"storage broke: {e}"[:120]
    dest = Path(app.root_path).parent / "uploads"
    dest.mkdir(exist_ok=True)
    (dest / name).write_bytes(data)
    return f"/uploads/{name}", None


def save_shot(app, f):
    if not f or not f.filename:
        return None, "no-file"
    ext = Path(f.filename).suffix.lower()
    if ext not in ext_ok:
        return None, "only png/jpg/webp/gif"
    data = f.read()
    if len(data) > app.config["MAX_CONTENT_LENGTH"]:
        return None, "too big (max 5mb)"
    if len(data) < 64 or _img_kind(data) not in ("png", "jpeg", "gif", "webp"):
        return None, "not a real image"
    return _store(app, data, ext)


def save_pres(app, f):
    if not f or not f.filename:
        return None, "no-file"
    ext = Path(f.filename).suffix.lower()
    if ext not in pres_ok:
        return None, "only pdf/ppt/pptx/key/zip/mp4/mov/webm"
    data = f.read()
    if len(data) > 20 * 1024 * 1024:
        return None, "too big (max 20mb)"
    if len(data) < 64:
        return None, "not a real file"
    head = data[:8]
    good = ((ext == ".pdf" and head[:4] == b"%PDF")
            or (ext in (".pptx", ".key", ".zip") and head[:2] == b"PK")
            or (ext == ".ppt" and head[:4] == b"\xd0\xcf\x11\xe0")
            or (ext in (".mp4", ".mov") and b"ftyp" in data[4:12])
            or (ext == ".webm" and head[:4] == b"\x1a\x45\xdf\xa3"))
    if not good:
        return None, "content does not match its type"
    return _store(app, data, ext)


def load_bytes(app, name):
    url, key = app.config["SUPABASE_URL"], app.config["SUPABASE_SERVICE_KEY"]
    if url and key:
        try:
            from supabase import create_client
            return create_client(url, key).storage.from_(app.config["UPLOAD_BUCKET"]).download(name)
        except Exception:
            return None
    p = Path(app.root_path).parent / "uploads" / Path(name).name
    return p.read_bytes() if p.exists() else None
