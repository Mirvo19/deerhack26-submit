from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

schema = """
create table if not exists rooms(
  id TEXT primary key, name TEXT not null, team_code TEXT not null unique,
  track TEXT not null default 'open', room TEXT not null default '', created_at TEXT not null);
create table if not exists submissions(
  id TEXT primary key, room_id TEXT not null unique references rooms(id) on delete cascade,
  title TEXT default '', tagline TEXT default '', description TEXT default '',
  description_html TEXT default '', github_url TEXT default '', demo_url TEXT default '',
  presentation_type TEXT default 'link', presentation_file TEXT default '', presentation_link TEXT default '',
  tech_stack TEXT default '[]', members TEXT default '[]',
  problem_statement TEXT default '', thumbnail_url TEXT default '',
  status TEXT default 'draft', submitted_at TEXT, updated_at TEXT not null);
create table if not exists github_cache(
  submission_id TEXT primary key references submissions(id) on delete cascade,
  repo_full_name TEXT, readme_html TEXT default '', commit_count INTEGER,
  last_commit_message TEXT, last_commit_author TEXT, last_commit_at TEXT,
  primary_language TEXT, stars INTEGER, repo_updated_at TEXT,
  fetch_error TEXT, fetched_at TEXT not null);
create table if not exists judges(uid TEXT primary key, name TEXT, email TEXT unique,
  password_hash TEXT, created_by TEXT, created_at TEXT, active INTEGER default 1);
create table if not exists mentors(uid TEXT primary key, name TEXT, email TEXT unique,
  password_hash TEXT, created_by TEXT, created_at TEXT, active INTEGER default 1);
create table if not exists admins(uid TEXT primary key, name TEXT, email TEXT unique,
  password_hash TEXT, created_by TEXT, created_at TEXT, active INTEGER default 1);
create table if not exists superadmins(uid TEXT primary key, name TEXT, email TEXT unique,
  password_hash TEXT, created_by TEXT, created_at TEXT, active INTEGER default 1);
create table if not exists scores(id TEXT primary key, submission_id TEXT not null,
  judge_uid TEXT not null, innovation INTEGER, execution INTEGER, impact INTEGER,
  presentation INTEGER, notes TEXT default '', created_at TEXT, updated_at TEXT);
create table if not exists audit_log(id TEXT primary key, actor_uid TEXT, actor_role TEXT,
  action TEXT not null, target TEXT, meta TEXT default '{}', created_at TEXT);
create table if not exists settings(key TEXT primary key, value TEXT not null, updated_at TEXT);
create index if not exists idx_scores_sub on scores(submission_id);
create index if not exists idx_audit_created on audit_log(created_at);
create index if not exists idx_sub_updated on submissions(updated_at);
create index if not exists idx_rooms_created on rooms(created_at);
"""

defaults = {
    "submission_deadline": "2030-01-01T00:00:00+00:00",
    "fields_deadline": "2030-01-01T00:00:00+00:00",
    "presentation_deadline": "2030-02-01T00:00:00+00:00",
    "tracks": ["open", "ai & data", "web & apps", "hardware & iot", "social good"],
    "event_name": "deerhack school edition 2026",
}

roles = ("judges", "mentors", "admins", "superadmins")
role_of = {"judges": "judge", "mentors": "mentor", "admins": "admin", "superadmins": "superadmin"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _mint(db):
    import secrets
    for _ in range(30):
        c = f"{secrets.choice(words)}-{secrets.choice(words)}-{secrets.randbelow(90) + 10}"
        if not db.room_by_code(c):
            return c
    raise RuntimeError("no code")


words = ("otter", "deer", "heron", "mole", "wren", "finch", "fox", "wolf", "bear", "lynx",
"owl", "hawk", "eagle", "falcon", "robin", "trout", "salmon", "pike", "crab", "coral",
"kelp", "pine", "oak", "maple", "birch", "cedar", "willow", "fern", "moss", "clover",
"sage", "mint", "lemon", "mango", "melon", "apple", "pear", "plum", "peach", "grape",
"comet", "planet", "rocket", "river", "brook", "lake", "pond", "wave", "tide", "reef",
"dune", "mesa", "frost", "snow", "hail", "storm", "ember", "flame", "spark", "ash",
"cloud", "rain", "wind", "stone", "pebble", "gem", "ruby", "opal", "jade", "pearl",
"drum", "flute", "banjo", "horn", "bell", "kite", "bike", "boat", "canoe", "kayak",
"sled", "train", "tram", "taxi", "jeep", "radar", "laser", "pixel", "chip", "modem",
"cable", "bulb", "lamp", "torch", "candle", "magnet", "map", "globe", "anchor", "oar",
"helmet", "boot", "glove", "scarf", "belt", "button", "pillow", "towel", "soap", "bucket",
"barrel", "crate", "chest", "trunk", "ladder", "bridge", "tower", "castle", "fort", "cabin",
"tent", "igloo", "temple", "shrine", "arch", "dome", "beacon", "acorn", "twig", "root",
"seed", "petal", "thorn", "honey", "wax", "silk", "wool", "paper", "poem", "tempo",
"beat", "tune", "song", "sketch", "stamp", "coin", "token", "medal", "ribbon", "badge",
"flag", "crest", "shield", "sword", "arrow", "bow", "harp", "lyre", "gong", "chime",
"kazoo", "mask", "cape", "crown", "orb", "wand", "charm", "cocoa", "chai", "latte",
"mocha", "juice", "cider", "soda", "candy", "fudge", "cookie", "bagel", "donut", "crepe",
"taco", "sushi", "ramen", "udon", "miso", "tofu", "pickle", "mayo", "pesto", "salsa",
"kebab", "grill", "wok", "mug", "cup", "glass", "vase", "jar", "tin", "cask",
"keg", "whisk", "ladle", "fork", "spoon", "knife", "plate", "bowl", "tray", "menu",
"chef", "tailor", "pilot", "sailor", "diver", "runner", "dancer", "singer", "poet", "author",
"editor", "scout", "ranger", "keeper", "guard", "mime", "actor", "encore", "haiku", "fable",
"myth", "saga", "epic", "psalm", "adage", "motto", "mantra", "zen", "sauna", "plunge",
"float", "soar", "sprint", "relay", "podium", "laurel", "olive", "daisy", "tulip", "rose",
"lily", "iris", "peony", "poppy", "aster", "lotus", "reed", "alder", "elm", "hazel",
"pecan", "flax", "bamboo", "slate", "tile", "brick", "eave", "gutter", "drain", "moat",
"ditch", "gorge", "gulch", "wadi", "creek", "delta", "fjord", "bay", "cove", "port",
"dock", "pier", "quay", "buoy", "fleet", "squad", "plaza", "alley", "lane", "tunnel",
"metro", "lobby", "foyer", "patio", "deck", "porch", "garden", "barn", "silo", "meadow",
"valley", "dale", "glen")


class localdb:
    def __init__(self, path):
        self._lock = threading.Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(schema)
            cols = [r[1] for r in self.conn.execute("pragma table_info(rooms)").fetchall()]
            if "room" not in cols:
                self.conn.execute("alter table rooms add column room TEXT not null default ''")
            subs = [r[1] for r in self.conn.execute("pragma table_info(submissions)").fetchall()]
            for cc, dd in (("presentation_type", "TEXT not null default 'link'"), ("presentation_file", "TEXT not null default ''"), ("presentation_link", "TEXT not null default ''")):
                if cc not in subs:
                    self.conn.execute(f"alter table submissions add column {cc} {dd}")
            if "slides_url" in subs:
                self.conn.execute("update submissions set presentation_link = slides_url where (presentation_link is null or presentation_link = '') and slides_url is not null and slides_url <> ''")
            old = self.conn.execute("select sql from sqlite_master where name='scores'").fetchone()
            if old and "unique" in (old[0] or "").lower():
                self.conn.executescript("alter table scores rename to scores_old; create table scores(id TEXT primary key, submission_id TEXT not null, judge_uid TEXT not null, innovation INTEGER, execution INTEGER, impact INTEGER, presentation INTEGER, notes TEXT default '', created_at TEXT, updated_at TEXT); insert into scores select * from scores_old; drop table scores_old;")
            for k, v in defaults.items():
                self.conn.execute(
                    "insert or ignore into settings(key,value,updated_at) values(?,?,?)",
                    (k, json.dumps(v), _now()),
                )
            self.conn.commit()

    def _q(self, sql, args=()):
        with self._lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def one(self, sql, args=()):
        with self._lock:
            return self.conn.execute(sql, args).fetchone()

    def all(self, sql, args=()):
        with self._lock:
            return self.conn.execute(sql, args).fetchall()

    def get_setting(self, key):
        r = self.one("select value from settings where key=?", (key,))
        if not r:
            return defaults.get(key)
        try:
            return json.loads(r["value"])
        except Exception:
            return r["value"]

    def get_many(self, *keys):
        out = {}
        if keys:
            ph = ",".join("?" * len(keys))
            for r in self.all(
                f"select key, value from settings where key in ({ph})", tuple(keys)
            ):
                try:
                    out[r["key"]] = json.loads(r["value"])
                except Exception:
                    out[r["key"]] = r["value"]
        for k in keys:
            out.setdefault(k, defaults.get(k))
        return out

    def set_setting(self, key, value):
        self._q(
            "insert into settings(key,value,updated_at) values(?,?,?)"
            " on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value), _now()),
        )

    def room_by_code(self, code):
        r = self.one("select * from rooms where team_code=?", ((code or "").strip(),))
        return dict(r) if r else None

    def room_by_id(self, rid):
        r = self.one("select * from rooms where id=?", (rid,))
        return dict(r) if r else None

    def list_rooms(self):
        return [dict(r) for r in self.all("select * from rooms order by created_at desc")]

    def create_room(self, name, track, room=""):
        rid, code = uuid.uuid4().hex, _mint(self)
        self._q(
            "insert into rooms(id,name,team_code,track,room,created_at) values(?,?,?,?,?,?)",
            (rid, name, code, track, room, _now()),
        )
        return self.room_by_id(rid)

    def update_room(self, rid, name, track, room=""):
        self._q("update rooms set name=?, track=?, room=? where id=?", (name, track, room, rid))

    def delete_room(self, rid):
        self._q("delete from rooms where id=?", (rid,))

    def submission_by_room(self, room_id):
        r = self.one("select * from submissions where room_id=?", (room_id,))
        return dict(r) if r else None

    def submission_by_id(self, sid):
        r = self.one("select * from submissions where id=?", (sid,))
        return dict(r) if r else None

    def ensure_submission(self, room_id):
        row = self.submission_by_room(room_id)
        if row:
            return row
        try:
            self._q(
                "insert into submissions(id,room_id,updated_at) values(?,?,?)",
                (uuid.uuid4().hex, room_id, _now()),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
        return self.submission_by_room(room_id)

    def save_submission(self, sid, fields):
        sets, args = [], []
        for c in ("title", "tagline", "description", "description_html", "github_url", "demo_url", "presentation_type", "presentation_file", "presentation_link", "tech_stack", "members", "problem_statement", "thumbnail_url", "status", "submitted_at"):
            if c in fields:
                v = fields[c]
                sets.append(f"{c}=?")
                args.append(json.dumps(v or []) if c in ("tech_stack", "members") else v)
        sets.append("updated_at=?")
        args += [_now(), sid]
        self._q(f"update submissions set {', '.join(sets)} where id=?", args)

    def list_submissions_full(self):
        return [dict(r) for r in self.all("select s.*, r.name as room_name, r.team_code, r.track as room_track, r.room as room from submissions s join rooms r on r.id=s.room_id order by s.updated_at desc")]

    def get_cache(self, sid):
        r = self.one("select * from github_cache where submission_id=?", (sid,))
        return dict(r) if r else None

    def put_cache(self, sid, p):
        cols = ["repo_full_name", "readme_html", "commit_count", "last_commit_message", "last_commit_author", "last_commit_at", "primary_language", "stars", "repo_updated_at", "fetch_error"]
        self._q("insert into github_cache(submission_id," + ",".join(cols) + ",fetched_at) values(?" + ",?" * len(cols) + ",?) on conflict(submission_id) do update set " + ", ".join(f"{c}=excluded.{c}" for c in cols) + ", fetched_at=excluded.fetched_at", [sid, *[p.get(c) for c in cols], _now()])

    def find_staff_by_email(self, email):
        for t in roles:
            r = self.one(f"select * from {t} where email=?", ((email or "").lower(),))
            if r:
                return {**dict(r), "role": role_of[t]}
        return None

    def find_staff_by_uid(self, uid):
        for t in roles:
            r = self.one(f"select * from {t} where uid=?", (uid,))
            if r:
                return {**dict(r), "role": role_of[t]}
        return None

    def email_taken(self, email):
        return self.find_staff_by_email(email) is not None

    def create_staff(self, role, uid, name, email, pw, by):
        self._q(f"insert into {role}(uid,name,email,password_hash,created_by,created_at,active) values(?,?,?,?,?,?,1)", (uid, name, email.lower(), pw, by, _now()))

    def set_staff_active(self, role, uid, on):
        self._q(f"update {role} set active=? where uid=?", (1 if on else 0, uid))

    def delete_staff(self, role, uid):
        self._q(f"delete from {role} where uid=?", (uid,))

    def list_staff(self, role):
        return [dict(r) for r in self.all(f"select * from {role} order by created_at desc")]

    def add_score(self, sid, uid, d):
        self._q(
            "insert into scores(id,submission_id,judge_uid,innovation,execution,impact,"
            "presentation,notes,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex, sid, uid,
                d.get("innovation"), d.get("execution"), d.get("impact"), d.get("presentation"),
                d.get("notes", ""), _now(), _now(),
            ),
        )

    def scores_for(self, sid):
        return [dict(r) for r in self.all("select * from scores where submission_id=? order by created_at desc", (sid,))]

    def all_scores(self):
        return [dict(r) for r in self.all("select * from scores", ())]

    def audit(self, uid, role, action, target=None, meta=None):
        self._q(
            "insert into audit_log(id,actor_uid,actor_role,action,target,meta,created_at)"
            " values(?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, uid, role, action, target, json.dumps(meta or {}), _now()),
        )

    def audit_list(self, limit=200):
        return [dict(r) for r in self.all("select * from audit_log order by created_at desc limit ?", (limit,))]


class supadb:
    def __init__(self, url, key):
        from supabase import create_client
        self.sb = create_client(url, key)

    def _t(self, n):
        return self.sb.table(n)

    def get_setting(self, key):
        r = self._t("settings").select("value").eq("key", key).limit(1).execute()
        return r.data[0]["value"] if r.data else defaults.get(key)

    def get_many(self, *keys):
        out = {}
        if keys:
            rows = self._t("settings").select("key,value").in_("key", list(keys)).execute().data or []
            for r in rows:
                out[r["key"]] = r["value"]
        for k in keys:
            out.setdefault(k, defaults.get(k))
        return out

    def set_setting(self, key, value):
        self._t("settings").upsert({"key": key, "value": value}).execute()

    def room_by_code(self, code):
        return _one(self._t("rooms").select("*").eq("team_code", (code or "").strip()).limit(1).execute())

    def room_by_id(self, rid):
        return _one(self._t("rooms").select("*").eq("id", rid).limit(1).execute())

    def list_rooms(self):
        return self._t("rooms").select("*").order("created_at", desc=True).execute().data or []

    def create_room(self, name, track, room=""):
        import secrets
        for _ in range(30):
            c = f"{secrets.choice(words)}-{secrets.choice(words)}-{secrets.randbelow(90) + 10}"
            try:
                self._t("rooms").insert({"name": name, "track": track, "room": room, "team_code": c}).execute()
                return self.room_by_code(c)
            except Exception:
                continue
        raise RuntimeError("no code")

    def update_room(self, rid, name, track, room=""):
        self._t("rooms").update({"name": name, "track": track, "room": room}).eq("id", rid).execute()

    def delete_room(self, rid):
        self._t("rooms").delete().eq("id", rid).execute()

    def submission_by_room(self, room_id):
        return _one(self._t("submissions").select("*").eq("room_id", room_id).limit(1).execute())

    def submission_by_id(self, sid):
        return _one(self._t("submissions").select("*").eq("id", sid).limit(1).execute())

    def ensure_submission(self, room_id):
        row = self.submission_by_room(room_id)
        if row:
            return row
        try:
            self._t("submissions").insert({"room_id": room_id}).execute()
        except Exception:
            pass
        row = self.submission_by_room(room_id)
        if row:
            return row
        raise RuntimeError("submission lost in a race, retry")

    def save_submission(self, sid, fields):
        self._t("submissions").update(fields).eq("id", sid).execute()

    def list_submissions_full(self):
        subs = self._t("submissions").select("*").order("updated_at", desc=True).execute().data or []
        rooms = {r["id"]: r for r in self._t("rooms").select("*").execute().data or []}
        return [{**s, "room_name": rooms.get(s["room_id"], {}).get("name", "-"), "team_code": "•••", "room_track": rooms.get(s["room_id"], {}).get("track", ""), "room": rooms.get(s["room_id"], {}).get("room", "")} for s in subs]

    def get_cache(self, sid):
        return _one(self._t("github_cache").select("*").eq("submission_id", sid).limit(1).execute())

    def put_cache(self, sid, p):
        self._t("github_cache").upsert({"submission_id": sid, **p}).execute()

    def find_staff_by_email(self, email):
        for t in roles:
            r = self._t(t).select("*").eq("email", (email or "").lower()).limit(1).execute()
            if r.data:
                return {**r.data[0], "role": role_of[t]}
        return None

    def find_staff_by_uid(self, uid):
        for t in roles:
            r = self._t(t).select("*").eq("uid", uid).limit(1).execute()
            if r.data:
                return {**r.data[0], "role": role_of[t]}
        return None

    def email_taken(self, email):
        return self.find_staff_by_email(email) is not None

    def create_staff(self, role, uid, name, email, pw, by):
        self._t(role).insert({"uid": uid, "name": name, "email": email.lower(), "created_by": by, "active": True}).execute()

    def set_staff_active(self, role, uid, on):
        self._t(role).update({"active": on}).eq("uid", uid).execute()

    def delete_staff(self, role, uid):
        self._t(role).delete().eq("uid", uid).execute()

    def list_staff(self, role):
        return self._t(role).select("*").order("created_at", desc=True).execute().data or []

    def add_score(self, sid, uid, d):
        self._t("scores").insert({"submission_id": sid, "judge_uid": uid, **d}).execute()

    def scores_for(self, sid):
        return self._t("scores").select("*").eq("submission_id", sid).order("created_at", desc=True).execute().data or []

    def all_scores(self):
        return self._t("scores").select("*").execute().data or []

    def audit(self, uid, role, action, target=None, meta=None):
        self._t("audit_log").insert({"actor_uid": uid, "actor_role": role, "action": action, "target": target, "meta": meta or {}}).execute()

    def audit_list(self, limit=200):
        return self._t("audit_log").select("*").order("created_at", desc=True).limit(limit).execute().data or []


def _transient(e):
    s = f"{type(e).__name__}: {e}".lower()
    return any(
        k in s
        for k in (
            "connect", "timeout", "timed out", "remoteprotocol", "pool",
            "temporar", "reset by peer", "broken pipe", "bad gateway",
            "service unavailable", "gateway timeout", "502", "503", "504",
        )
    )


_reads = (
    "get_setting", "get_many", "room_by_code", "room_by_id", "list_rooms",
    "submission_by_room", "submission_by_id", "list_submissions_full",
    "get_cache", "find_staff_by_email", "find_staff_by_uid", "email_taken",
    "list_staff", "scores_for", "all_scores", "audit_list",
)

for _name in _reads:
    _fn = getattr(supadb, _name)

    @wraps(_fn)
    def _wrapped(*a, _fn=_fn, **kw):
        try:
            return _fn(*a, **kw)
        except Exception as e:
            if not _transient(e):
                raise
            time.sleep(0.3)
            return _fn(*a, **kw)

    setattr(supadb, _name, _wrapped)
del _name, _fn, _wrapped


def _one(res):
    return dict(res.data[0]) if res.data else None


_db = None


def get_db(app=None):
    global _db
    if _db is not None:
        return _db
    url = app.config["SUPABASE_URL"].strip() if app else ""
    key = app.config["SUPABASE_SERVICE_KEY"].strip() if app else ""
    _db = supadb(url, key) if url and key else localdb(app.config["LOCAL_DB_PATH"] if app else "deerhack.db")
    return _db
