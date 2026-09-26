from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_lost = db.query(models.Report).filter(models.Report.kind == models.ReportKind.lost).count()
    total_found = db.query(models.Report).filter(models.Report.kind == models.ReportKind.found).count()
    potential_matches = db.query(models.Match).filter(models.Match.status == models.MatchStatus.suggested).count()
    matches_confirmed = db.query(models.Match).filter(models.Match.status == models.MatchStatus.confirmed).count()
    items_returned = db.query(models.Report).filter(models.Report.status == models.ReportStatus.returned).count()

    total_matches = db.query(models.Match).count()
    success_rate = round((matches_confirmed / total_matches) * 100, 1) if total_matches else 0.0

    # Activity over time: reports created per day (last N days worth of data present)
    reports = db.query(models.Report.created_at, models.Report.kind).all()
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"lost": 0, "found": 0})
    for created_at, kind in reports:
        day = created_at.strftime("%Y-%m-%d") if isinstance(created_at, datetime) else str(created_at)[:10]
        by_day[day][kind.value if hasattr(kind, "value") else kind] += 1

    activity = [
        {"date": day, "lost": counts["lost"], "found": counts["found"]}
        for day, counts in sorted(by_day.items())
    ]

    return schemas.DashboardStats(
        total_lost=total_lost,
        total_found=total_found,
        potential_matches=potential_matches,
        matches_confirmed=matches_confirmed,
        items_returned=items_returned,
        success_rate_pct=success_rate,
        activity_over_time=activity,
    )
