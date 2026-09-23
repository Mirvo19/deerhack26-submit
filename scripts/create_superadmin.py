import sys

sys.path.insert(0, ".")

from werkzeug.security import generate_password_hash

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
        g.db = get_db(app)
        if g.db.email_taken(email):
            print("mail taken")
            sys.exit(1)
        import uuid
        g.db.create_staff(
            "superadmins", uuid.uuid4().hex, name, email, generate_password_hash(pw), None,
        )
        print(f"superadmin {email} live. hit {app.config['STAFF_LOGIN_PATH']}")


if __name__ == "__main__":
    main()
