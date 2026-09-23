import os


def _int(n, d):
    try:
        return int(os.environ.get(n, d))
    except (TypeError, ValueError):
        return d


class cfg:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    STAFF_LOGIN_PATH = (
        os.environ.get("STAFF_LOGIN_PATH", "/dh-den-9x4k-entry").strip()
        or "/dh-den-9x4k-entry"
    )
    MAX_CONTENT_LENGTH = _int("MAX_BODY_MB", 52) * 1024 * 1024
    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 5)
    UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "submission-assets")
    GITHUB_CACHE_TTL_MIN = _int("GITHUB_CACHE_TTL_MIN", 10)

    @property
    def use_supabase(self):
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)
