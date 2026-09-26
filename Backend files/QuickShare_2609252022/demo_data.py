"""
Demo Data generator ("Hackathon Demo Mode").

Creates a couple of demo users and a realistic set of lost/found reports --
including the canonical "Black Lenovo ThinkPad near Block B" pair from the
product spec -- then runs the REAL matching engine against them (nothing
here hard-codes an 87% result; the score you see is calculated live from
these fields, so if you edit the demo text the score will change too).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models, auth


def _get_or_create_demo_user(db: Session, email: str, name: str) -> models.User:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        return user
    user = models.User(
        name=name,
        email=email,
        hashed_password=auth.hash_password("demo12345"),
        contact_method="email",
        contact_value=email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


DEMO_LOST_ITEMS = [
    dict(
        item_name="Black Lenovo ThinkPad Laptop",
        category="laptop", brand="Lenovo", model="ThinkPad T14",
        color="black",
        description="Lost my black Lenovo laptop near Block B. It has a small silver sticker on the top-right corner of the lid.",
        distinguishing_features="Small silver sticker on top-right corner of the lid, minor scratch near the hinge",
        location_text="Near Block B, main campus",
        latitude=9.9252, longitude=78.1198,
        hours_ago=3.5,
    ),
    dict(
        item_name="Blue Backpack",
        category="bag", brand="Wildcraft", model=None, color="blue",
        description="Navy blue backpack with a laptop compartment, lost in the library reading hall.",
        distinguishing_features="Keychain of a small panda hanging from the front zip",
        location_text="Central Library, 2nd floor",
        latitude=9.9260, longitude=78.1210,
        hours_ago=20,
    ),
    dict(
        item_name="Wallet with College ID",
        category="wallet", brand=None, model=None, color="brown",
        description="Brown leather wallet containing my college ID card and a debit card.",
        distinguishing_features="Frayed stitching on one edge, initials 'R.K.' embossed inside",
        location_text="Cafeteria near Block C",
        latitude=9.9245, longitude=78.1225,
        hours_ago=48,
    ),
]

DEMO_FOUND_ITEMS = [
    dict(
        item_name="Black Lenovo Laptop",
        category="laptop", brand="Lenovo", model="ThinkPad",
        color="black",
        description="Found a black Lenovo laptop near Block B, left on a bench.",
        distinguishing_features="Has a silver sticker on the corner of the lid",
        location_text="Near Block B entrance",
        latitude=9.9253, longitude=78.1199,
        hours_ago=2.5,
    ),
    dict(
        item_name="Black Backpack",
        category="bag", brand=None, model=None, color="black",
        description="Found a plain black backpack near the sports ground, no tags visible.",
        distinguishing_features="Small hole in the bottom seam",
        location_text="Sports ground",
        latitude=9.9300, longitude=78.1150,
        hours_ago=10,
    ),
    dict(
        item_name="Brown Wallet",
        category="wallet", brand=None, model=None, color="brown",
        description="Found a worn brown wallet with a college ID inside, near the cafeteria.",
        distinguishing_features="Stitching coming apart on one side",
        location_text="Cafeteria, Block C",
        latitude=9.9246, longitude=78.1226,
        hours_ago=44,
    ),
]


def seed_demo_data(db: Session) -> dict:
    lost_owner = _get_or_create_demo_user(db, "priya.demo@findback.ai", "Priya (Demo)")
    found_owner = _get_or_create_demo_user(db, "arjun.demo@findback.ai", "Arjun (Demo)")

    now = datetime.now(timezone.utc)
    created_lost, created_found = [], []

    for item in DEMO_LOST_ITEMS:
        report = models.Report(
            owner_id=lost_owner.id,
            kind=models.ReportKind.lost,
            status=models.ReportStatus.active,
            item_name=item["item_name"], category=item["category"],
            description=item["description"], brand=item["brand"], model=item["model"],
            color=item["color"], distinguishing_features=item["distinguishing_features"],
            location_text=item["location_text"], latitude=item["latitude"], longitude=item["longitude"],
            event_time=now - timedelta(hours=item["hours_ago"]),
            contact_method="In-app message",
        )
        db.add(report)
        created_lost.append(report)

    for item in DEMO_FOUND_ITEMS:
        report = models.Report(
            owner_id=found_owner.id,
            kind=models.ReportKind.found,
            status=models.ReportStatus.active,
            item_name=item["item_name"], category=item["category"],
            description=item["description"], brand=item["brand"], model=item["model"],
            color=item["color"], distinguishing_features=item["distinguishing_features"],
            location_text=item["location_text"], latitude=item["latitude"], longitude=item["longitude"],
            event_time=now - timedelta(hours=item["hours_ago"]),
            contact_method="In-app message",
        )
        db.add(report)
        created_found.append(report)

    db.commit()
    for r in created_lost + created_found:
        db.refresh(r)

    # Run the real matching engine for every new lost report against every found report.
    from app.matching.engine import compute_match, report_to_fields
    matches_created = []
    for lost in created_lost:
        for found in created_found:
            result = compute_match(report_to_fields(lost), report_to_fields(found))
            if result["score"] < 20:
                continue
            match = models.Match(
                lost_report_id=lost.id, found_report_id=found.id,
                score=result["score"], factors=result["factors"], reasons=result["reasons"],
                status=models.MatchStatus.suggested,
            )
            db.add(match)
            matches_created.append(match)
            for r in (lost, found):
                if r.status == models.ReportStatus.active:
                    r.status = models.ReportStatus.possible_match
    db.commit()

    return {
        "users_created_or_reused": [lost_owner.email, found_owner.email],
        "lost_reports_created": len(created_lost),
        "found_reports_created": len(created_found),
        "matches_created": len(matches_created),
        "top_match_score": max((m.score for m in matches_created), default=0),
    }
