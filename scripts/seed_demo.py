import sys

sys.path.insert(0, ".")

from portal import create_app
from portal.db import get_db

demos = [
    ("pixel hawks", "web & apps", "lab 1 - table 1"),
    ("circuit deer", "hardware & iot", "lab 1 - table 2"),
    ("data antlers", "ai & data", "lab 2 - table 1"),
    ("kind code", "social good", "lab 2 - table 2"),
]


def main():
    app = create_app()
    with app.app_context():
        from flask import g
        g.db = get_db(app)
        for name, track, loc in demos:
            room = g.db.create_room(name, track, loc)
            g.db.ensure_submission(room["id"])
            print(f"{name:15s}  /submit/{room['team_code']}")


if __name__ == "__main__":
    main()
