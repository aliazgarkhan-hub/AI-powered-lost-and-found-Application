"""
Run this directly to populate the database with demo data without starting
the server:

    python seed_demo_data.py

It's the same logic the "Demo Data" button (POST /api/demo/seed) calls.
"""
from app.database import SessionLocal, init_db
from app.demo_data import seed_demo_data

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        summary = seed_demo_data(db)
        print("Demo data seeded:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
    finally:
        db.close()
