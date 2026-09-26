from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from difflib import SequenceMatcher

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/moderation", response_model=list[schemas.ModerationTicketOut])
def list_moderation_tickets(
    status: str | None = None,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(auth.get_current_admin),
):
    q = db.query(models.ModerationTicket)
    if status:
        q = q.filter(models.ModerationTicket.status == status)
    return q.order_by(models.ModerationTicket.created_at.desc()).all()


@router.post("/moderation", response_model=schemas.ModerationTicketOut, status_code=201)
def flag_content(
    payload: schemas.ModerationTicketCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Report fraudulent listing / inappropriate content -- any signed-in user."""
    ticket = models.ModerationTicket(
        target_type=payload.target_type,
        target_id=payload.target_id,
        reporter_id=current_user.id,
        reason=payload.reason,
        details=payload.details,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/moderation/{ticket_id}", response_model=schemas.ModerationTicketOut)
def resolve_ticket(
    ticket_id: str,
    payload: schemas.ModerationDecision,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(auth.get_current_admin),
):
    ticket = db.query(models.ModerationTicket).filter(models.ModerationTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = payload.status
    if payload.action == "close_report" and ticket.target_type == models.ModerationTargetType.report:
        report = db.query(models.Report).filter(models.Report.id == ticket.target_id).first()
        if report:
            report.status = models.ReportStatus.closed
            report.is_flagged = True
            report.flag_reason = ticket.reason
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/duplicates", response_model=list[dict])
def detect_duplicates(
    kind: models.ReportKind,
    threshold: float = 0.85,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(auth.get_current_admin),
):
    """Simple duplicate-report detection: compares same-kind reports pairwise
    using the matching engine's text similarity plus a name-similarity check,
    surfacing pairs above `threshold`. For a hackathon-scale dataset this
    O(n^2) scan is fine; swap for a vector index (e.g. FAISS) at real scale."""
    reports = db.query(models.Report).filter(models.Report.kind == kind).all()
    duplicates = []
    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            a, b = reports[i], reports[j]
            if a.owner_id != b.owner_id:
                continue  # duplicates are only meaningful within the same reporter
            name_sim = SequenceMatcher(None, (a.item_name or "").lower(), (b.item_name or "").lower()).ratio()
            if name_sim >= threshold:
                duplicates.append({
                    "report_a": a.id, "report_b": b.id,
                    "item_name": a.item_name, "similarity": round(name_sim, 3),
                })
    return duplicates


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(auth.get_current_admin)):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()
