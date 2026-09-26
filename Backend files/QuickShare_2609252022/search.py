from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routers import reports_common as common

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[schemas.ReportOut])
def search_reports(
    q: Optional[str] = None,
    kind: Optional[models.ReportKind] = None,   # lost | found
    category: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[models.ReportStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Powers the Browse Reports page: category / brand / color / location /
    date / lost-vs-found filters, plus a free-text `q` over item name."""
    results = common.list_reports(
        db, kind=kind, category=category, brand=brand, color=color,
        location=location, status=status, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    if q:
        needle = q.lower()
        results = [
            r for r in results
            if needle in (r.item_name or "").lower()
            or needle in (r.description or "").lower()
            or needle in (r.distinguishing_features or "").lower()
        ]
    return results
