from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.routers import reports_common as common

router = APIRouter(prefix="/api/found", tags=["found reports"])


@router.post("", response_model=schemas.ReportOut, status_code=201)
def report_found_item(
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
    """Report a Found Item: photo, item name/category, description, location
    found, date/time found, visible brand/model, distinguishing features,
    contact method -- same agreed shape as /api/lost, kind flipped."""
    report = common.create_report(
        db, current_user.id, models.ReportKind.found,
        item_name, category, description, brand, model, color,
        distinguishing_features, location_text, latitude, longitude,
        event_time, contact_method, photo,
    )
    return report


@router.get("", response_model=list[schemas.ReportOut])
def list_found_items(
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
        db, kind=models.ReportKind.found, category=category, brand=brand,
        color=color, location=location, status=status, limit=limit, offset=offset,
    )


@router.get("/{report_id}", response_model=schemas.ReportOut)
def get_found_item(report_id: str, db: Session = Depends(get_db)):
    report = common.get_report_or_404(db, report_id)
    if report.kind != models.ReportKind.found:
        raise HTTPException(status_code=404, detail="Not a found report")
    return report


@router.patch("/{report_id}/status", response_model=schemas.ReportOut)
def update_found_status(
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
