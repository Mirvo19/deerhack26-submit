import sys

sys.path.insert(0, ".")

from portal import create_app
from portal.db import get_db


def main():
    if len(sys.argv) != 4:
        print('use: python scripts/create_superadmin.py "name" mail pw')
        sys.exit(1)
    name, email, pw = sys.argv[1], sys.argv[2].lower(), sys.argv[3]
    if len(pw) < 10:
        print("pw must be 10+")
        sys.exit(1)
    app = create_app()
    with app.app_context():
        from flask import g
        from supabase import create_client
        g.db = get_db(app)
        if g.db.email_taken(email):
            print("mail taken")
            sys.exit(1)
        sb = create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_SERVICE_KEY"])
        uid = sb.auth.admin.create_user({"email": email, "password": pw, "email_confirm": True}).user.id
        g.db.create_staff("superadmins", uid, name, email, None, None)
        print(f"superadmin {email} live. log in at {app.config['STAFF_LOGIN_PATH']}")


if __name__ == "__main__":
    main()
