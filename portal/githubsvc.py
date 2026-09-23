from __future__ import annotations

import base64
import re
from datetime import datetime, timezone

import requests

from .utils import gh_split, md_safe

ua = {"user-agent": "deerhack-school-2026", "accept": "application/vnd.github+json"}
tmo = 12


def _get(url):
    r = requests.get(url, headers=ua, timeout=tmo)
    if r.status_code == 404:
        return None, "not-found"
    if r.status_code == 403 and "rate limit" in r.text.lower():
        return None, "rate-limited"
    r.raise_for_status()
    return r.json(), None


def snap(url):
    g = gh_split(url or "")
    if not g:
        return {"fetch_error": "invalid-url"}
    o, repo = g
    try:
        meta, err = _get(f"https://api.github.com/repos/{o}/{repo}")
        if err or not meta:
            return {"fetch_error": err or "fetch-failed"}
        if meta.get("private"):
            return {"fetch_error": "repo-is-private"}
        readme = ""
        try:
            rm = requests.get(f"https://api.github.com/repos/{o}/{repo}/readme", headers=ua, timeout=tmo)
            if rm.status_code == 200:
                raw = base64.b64decode(rm.json().get("content", "") or "").decode("utf-8", errors="replace")
                readme = md_safe(raw[:60000])
        except Exception:
            pass
        n, msg, who, when = None, None, None, None
        try:
            c = requests.get(f"https://api.github.com/repos/{o}/{repo}/commits?per_page=1", headers=ua, timeout=tmo)
            if c.status_code == 200 and c.json():
                top = c.json()[0]
                msg = (top.get("commit", {}).get("message") or "")[:300]
                who = (top.get("commit", {}).get("author") or {}).get("name") or top.get("author", {}).get("login")
                when = (top.get("commit", {}).get("author") or {}).get("date")
                m = re.search(r"[?&]page=(\d+)>; rel=\"last\"", c.headers.get("link", ""))
                n = int(m.group(1)) if m else 1
        except Exception:
            pass
        return {"repo_full_name": f"{o}/{repo}", "readme_html": readme, "commit_count": n,
                "last_commit_message": msg, "last_commit_author": who, "last_commit_at": when,
                "primary_language": (meta.get("language") or "").lower() or None,
                "stars": meta.get("stargazers_count"), "repo_updated_at": meta.get("pushed_at") or meta.get("updated_at"),
                "fetch_error": None}
    except requests.RequestException as e:
        return {"fetch_error": f"github-error: {e.__class__.__name__.lower()}"}


def stale(at, ttl):
    if not at:
        return True
    try:
        dt = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60 > ttl
    except Exception:
        return True


def refresh(db, sub, ttl, force=False):
    sid, url = sub["id"], sub.get("github_url")
    cache = db.get_cache(sid)
    if cache and not force and not stale(cache.get("fetched_at"), ttl):
        return cache
    if not url:
        return cache
    db.put_cache(sid, snap(url))
    return db.get_cache(sid)


def reachable(url):
    g = gh_split(url or "")
    if not g:
        return False, "url must look like https://github.com/owner/repo"
    try:
        meta, err = _get(f"https://api.github.com/repos/{g[0]}/{g[1]}")
        if err == "not-found":
            return False, "repo not found - typo, renamed, deleted?"
        if err == "rate-limited":
            return True, "warn: github rate limit hit, will re-check later"
        if not meta:
            return False, "could not reach github -retry"
        if meta.get("private"):
            return False, "repo looks private -make it public"
        return True, "ok"
    except Exception:
        return False, "could not reach github -retry in a bit"
