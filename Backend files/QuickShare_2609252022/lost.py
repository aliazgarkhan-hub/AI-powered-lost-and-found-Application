from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.routers import reports_common as common

router = APIRouter(prefix="/api/lost", tags=["lost reports"])


@router.post("", response_model=schemas.ReportOut, status_code=201)
def report_lost_item(
    item_name: str = Form(...),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    distinguishing_features: Optional[str] = Form(None),
    location_text: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    event_time: Optional[datetime] = Form(None),
    contact_method: Optional[str] = Form("In-app message"),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Report a Lost Item. Matches the agreed frontend fields exactly:
    item name, description, brand, color, model, distinguishing features,
    last known location, date/time lost, optional photo, contact method."""
    report = common.create_report(
        db, current_user.id, models.ReportKind.lost,
        item_name, category, description, brand, model, color,
        distinguishing_features, location_text, latitude, longitude,
        event_time, contact_method, photo,
    )
    return report


@router.get("", response_model=list[schemas.ReportOut])
def list_lost_items(
    category: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[models.ReportStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return common.list_reports(
        db, kind=models.ReportKind.lost, category=category, brand=brand,
        color=color, location=location, status=status, limit=limit, offset=offset,
    )


@router.get("/{report_id}", response_model=schemas.ReportOut)
def get_lost_item(report_id: str, db: Session = Depends(get_db)):
    report = common.get_report_or_404(db, report_id)
    if report.kind != models.ReportKind.lost:
        raise HTTPException(status_code=404, detail="Not a lost report")
    return report


@router.patch("/{report_id}/status", response_model=schemas.ReportOut)
def update_lost_status(
    report_id: str,
    payload: schemas.ReportStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    report = common.get_report_or_404(db, report_id)
    if report.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not your report")
    report.status = payload.status
    db.commit()
    db.refresh(report)
    return report
