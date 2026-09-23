from __future__ import annotations

import time
from functools import wraps

defaults = {
    "submission_deadline": "2030-01-01T00:00:00+00:00",
    "fields_deadline": "2030-01-01T00:00:00+00:00",
    "presentation_deadline": "2030-02-01T00:00:00+00:00",
    "tracks": ["open", "ai & data", "web & apps", "hardware & iot", "social good"],
    "event_name": "deerhack school edition 2026",
}

roles = ("judges", "mentors", "admins", "superadmins")
role_of = {"judges": "judge", "mentors": "mentor", "admins": "admin", "superadmins": "superadmin"}

settings_ttl = 60
staff_ttl = 30


def _cacheable(key):
    return not key.endswith("deadline")


def _fresh_code(check):
    import secrets
    for _ in range(30):
        c = f"{secrets.choice(words)}-{secrets.choice(words)}-{secrets.randbelow(90) + 10}"
        if not check(c):
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


class supadb:
    def __init__(self, url, key):
        from supabase import create_client
        self.sb = create_client(url, key)
        self._scache = {}
        self._staffcache = {}

    def _t(self, n):
        return self.sb.table(n)

    def _mem(self, store, key, ttl):
        hit = store.get(key)
        if hit and time.time() - hit[1] < ttl:
            return hit[0], True
        return None, False

    def get_setting(self, key):
        if _cacheable(key):
            v, ok = self._mem(self._scache, key, settings_ttl)
            if ok:
                return v
        r = self._t("settings").select("value").eq("key", key).limit(1).execute()
        v = r.data[0]["value"] if r.data else defaults.get(key)
        if _cacheable(key):
            self._scache[key] = (v, time.time())
        return v

    def get_many(self, *keys):
        out = {}
        missing = []
        for k in keys:
            if _cacheable(k):
                v, ok = self._mem(self._scache, k, settings_ttl)
                if ok:
                    out[k] = v
                    continue
            missing.append(k)
        if missing:
            rows = self._t("settings").select("key,value").in_("key", missing).execute().data or []
            for r in rows:
                out[r["key"]] = r["value"]
                if _cacheable(r["key"]):
                    self._scache[r["key"]] = (r["value"], time.time())
        for k in keys:
            out.setdefault(k, defaults.get(k))
        return out

    def set_setting(self, key, value):
        self._scache.pop(key, None)
        self._t("settings").upsert({"key": key, "value": value}).execute()

    def room_by_code(self, code):
        return _one(self._t("rooms").select("*").eq("team_code", (code or "").strip()).limit(1).execute())

    def room_by_id(self, rid):
        return _one(self._t("rooms").select("*").eq("id", rid).limit(1).execute())

    def list_rooms(self):
        return self._t("rooms").select("*").order("created_at", desc=True).execute().data or []

    def create_room(self, name, track, room=""):
        for _ in range(30):
            c = _fresh_code(self.room_by_code)
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
        v, ok = self._mem(self._staffcache, uid, staff_ttl)
        if ok:
            return v
        for t in roles:
            r = self._t(t).select("*").eq("uid", uid).limit(1).execute()
            if r.data:
                row = {**r.data[0], "role": role_of[t]}
                self._staffcache[uid] = (row, time.time())
                return row
        return None

    def email_taken(self, email):
        return self.find_staff_by_email(email) is not None

    def create_staff(self, role, uid, name, email, pw, by):
        self._t(role).insert({"uid": uid, "name": name, "email": email.lower(), "created_by": by, "active": True}).execute()

    def set_staff_active(self, role, uid, on):
        self._staffcache.pop(uid, None)
        self._t(role).update({"active": on}).eq("uid", uid).execute()

    def delete_staff(self, role, uid):
        self._staffcache.pop(uid, None)
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
    if not (url and key):
        raise RuntimeError("supabase not configured - set supabase_url + supabase_service_key")
    _db = supadb(url, key)
    return _db
