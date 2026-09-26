"""Shared logic behind /api/lost and /api/found so both routers stay tiny
and consistent -- one code path, two entry points (kind=lost / kind=found)."""
import os
from datetime import datetime
from typing import Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.storage import storage
from app.matching.image_analysis import analyze_image
from app.config import settings


def create_report(
    db: Session,
    owner_id: str,
    kind: models.ReportKind,
    item_name: str,
    category: Optional[str],
    description: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    color: Optional[str],
    distinguishing_features: Optional[str],
    location_text: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    event_time: Optional[datetime],
    contact_method: Optional[str],
    photo: Optional[UploadFile],
) -> models.Report:
    if not item_name or not item_name.strip():
        raise HTTPException(status_code=422, detail="item_name is required")

    photo_url = None
    image_features = None
    if photo is not None and photo.filename:
        stored_name = storage.save(photo)
        photo_url = storage.url_for(stored_name)
        full_path = os.path.join(settings.UPLOAD_DIR, stored_name)
        try:
            image_features = analyze_image(full_path)
        except Exception:
            image_features = None

    report = models.Report(
        owner_id=owner_id,
        kind=kind,
        item_name=item_name.strip(),
        category=(category or "").strip().lower() or None,
        description=description,
        brand=brand,
        model=model,
        color=(color or "").strip().lower() or None,
        distinguishing_features=distinguishing_features,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        event_time=event_time,
        contact_method=contact_method or "In-app message",
        photo_url=photo_url,
        image_features=image_features,
        status=models.ReportStatus.active,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(
    db: Session,
    kind: Optional[models.ReportKind] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[models.ReportStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    owner_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Report)
    if kind:
        q = q.filter(models.Report.kind == kind)
    if category:
        q = q.filter(models.Report.category.ilike(f"%{category.lower()}%"))
    if brand:
        q = q.filter(models.Report.brand.ilike(f"%{brand}%"))
    if color:
        q = q.filter(models.Report.color.ilike(f"%{color.lower()}%"))
    if location:
        q = q.filter(models.Report.location_text.ilike(f"%{location}%"))
    if status:
        q = q.filter(models.Report.status == status)
    if date_from:
        q = q.filter(models.Report.event_time >= date_from)
    if date_to:
        q = q.filter(models.Report.event_time <= date_to)
    if owner_id:
        q = q.filter(models.Report.owner_id == owner_id)
    q = q.order_by(models.Report.created_at.desc())
    return q.offset(offset).limit(limit).all()


def get_report_or_404(db: Session, report_id: str) -> models.Report:
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
