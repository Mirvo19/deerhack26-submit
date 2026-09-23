from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import bleach
import markdown as md

npt = timezone(timedelta(hours=5, minutes=45))

gh_re = re.compile(r"^https?://(www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?(?:[?#].*)?$")

tags_ok = list(bleach.sanitizer.ALLOWED_TAGS) + [
    "p", "pre", "code", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td", "hr", "br",
    "img", "input", "details", "summary",
]
attrs_ok = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "input": ["type", "checked", "disabled"],
    "code": ["class"],
    "pre": ["class"],
    "th": ["align"],
    "td": ["align"],
}


def md_safe(raw):
    html = md.markdown(raw or "", extensions=["fenced_code", "tables", "toc"])
    return bleach.linkify(bleach.clean(html, tags=tags_ok, attributes=attrs_ok, strip=True))


def gh_split(url):
    m = gh_re.match((url or "").strip())
    if not m or m.group(2).lower() in ("settings", "orgs", "marketplace", "notifications"):
        return None
    return m.group(2), m.group(3)


def http_ok(url):
    try:
        p = urlparse((url or "").strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def deadline_at(v):
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def locked(v):
    dt = deadline_at(v)
    return datetime.now(timezone.utc) >= dt if dt else False


def deadline_for(db, key):
    return db.get_setting(key) or db.get_setting("submission_deadline")


def deadlines(db):
    s = db.get_many("tracks", "fields_deadline", "presentation_deadline")
    if not s.get("fields_deadline") or not s.get("presentation_deadline"):
        leg = db.get_setting("submission_deadline")
        s["fields_deadline"] = s.get("fields_deadline") or leg
        s["presentation_deadline"] = s.get("presentation_deadline") or leg
    return s


def _dt(v):
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def f_npt(v):
    dt = _dt(v)
    return dt.astimezone(npt).strftime("%Y-%m-%d %H:%M npt") if dt else "-"


def f_nptlocal(v):
    dt = _dt(v)
    return dt.astimezone(npt).strftime("%Y-%m-%dT%H:%M") if dt else ""


def npt_to_utc(s):
    try:
        naive = datetime.strptime((s or "").strip(), "%Y-%m-%dT%H:%M")
    except Exception:
        return None
    return naive.replace(tzinfo=npt).astimezone(timezone.utc)


def csv_list(s):
    seen, out = set(), []
    for p in re.split(r"[,\n]", s or ""):
        p = p.strip().lower()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out[:30]


def score_n(v):
    try:
        return max(1, min(10, int(v)))
    except (TypeError, ValueError):
        return None
