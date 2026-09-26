from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, auth
from app.routers.reports_common import get_report_or_404

router = APIRouter(prefix="/api/reports", tags=["recovery"])


class RecoveryConfirm(BaseModel):
    confirm: bool = True


@router.post("/{report_id}/mark-recovered")
def mark_recovered(
    report_id: str,
    payload: RecoveryConfirm,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Owner marks their item as Recovered/Returned. Requires an explicit
    confirmation flag from the client (the UI should show a confirm dialog
    before calling this) rather than a silent status flip."""
    report = get_report_or_404(db, report_id)
    if report.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not your report")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirmation required to mark as recovered")

    report.status = models.ReportStatus.returned
    db.commit()
    db.refresh(report)

    # Close out any open matches tied to this report -- it's resolved now.
    open_matches = (
        db.query(models.Match)
        .filter(
            ((models.Match.lost_report_id == report.id) | (models.Match.found_report_id == report.id)),
            models.Match.status == models.MatchStatus.suggested,
        )
        .all()
    )
    for m in open_matches:
        m.status = models.MatchStatus.confirmed
    db.commit()

    return {"id": report.id, "status": report.status}
