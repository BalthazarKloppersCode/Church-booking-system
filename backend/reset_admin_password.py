"""
Last-resort recovery when no admin can log in (for example the only admin forgot
their password). Run it on your own computer, from the backend folder, with
backend/.env pointing at the live database:

    python reset_admin_password.py

It asks which admin and for a new password (typed hidden, never printed or
stored anywhere except as a hash in the database). That admin's existing
sessions are signed out. If another admin can still log in, they can do this from
the portal instead (Admin -> My account -> Other admins).
"""
import getpass
import sys
from datetime import datetime

from pymongo import MongoClient

from app.auth import hash_password
from app.config import settings


def main() -> int:
    admins = MongoClient(settings.mongo_uri)[settings.mongo_db_name]["admins"]
    emails = sorted(a["email"] for a in admins.find({}, {"email": 1}))
    if not emails:
        print("There are no admin accounts yet — create the first one with the setup secret instead (see README).")
        return 1
    print("Admin accounts:", ", ".join(emails))
    email = input("Reset the password for which admin email? ").strip()
    admin = admins.find_one({"email": email})
    if not admin:
        print("No admin with that email — nothing changed.")
        return 1

    password = getpass.getpass("New password (8-72 characters, hidden): ")
    if getpass.getpass("Type it again: ") != password:
        print("The two didn't match — nothing changed.")
        return 1
    if not 8 <= len(password) <= 72:
        print("The password must be 8 to 72 characters — nothing changed.")
        return 1

    admins.update_one(
        {"_id": admin["_id"]},
        {"$set": {"password_hash": hash_password(password), "password_changed_at": datetime.utcnow()}},
    )
    print(f"Done — {email} can now log in with the new password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
