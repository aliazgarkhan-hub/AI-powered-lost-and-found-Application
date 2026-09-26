"""
Create (or promote) an admin user for the Admin/Moderation Dashboard.

    python create_admin.py admin@example.com "Admin Name" somepassword123
"""
import sys
from app.database import SessionLocal, init_db
from app import models, auth


def main():
    if len(sys.argv) != 4:
        print("Usage: python create_admin.py <email> <name> <password>")
        sys.exit(1)

    email, name, password = sys.argv[1].lower(), sys.argv[2], sys.argv[3]
    init_db()
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.is_admin = True
            print(f"Promoted existing user {email} to admin.")
        else:
            user = models.User(
                name=name, email=email,
                hashed_password=auth.hash_password(password),
                is_admin=True, contact_method="email", contact_value=email,
            )
            db.add(user)
            print(f"Created new admin user {email}.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
