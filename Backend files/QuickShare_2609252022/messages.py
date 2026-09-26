from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.routers.reports_common import get_report_or_404

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.post("", response_model=schemas.ContactRequestOut, status_code=201)
def send_contact_request(
    payload: schemas.ContactRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    In-app 'Someone is interested in your item' request.
    We NEVER expose the recipient's email/phone here -- only a message plus
    a notification. The recipient chooses whether to respond (accept/decline).
    """
    report = get_report_or_404(db, payload.report_id)
    if report.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't contact yourself about your own report")

    cr = models.ContactRequest(
        report_id=report.id,
        match_id=payload.match_id,
        sender_id=current_user.id,
        recipient_id=report.owner_id,
        message_text=payload.message_text or "Someone is interested in your item.",
        status=models.MessageStatus.pending,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return _hydrate(db, cr, current_user.id)


@router.get("", response_model=list[schemas.ContactRequestOut])
def list_my_messages(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Inbox + sent, for the Messages/Contact Requests page."""
    rows = (
        db.query(models.ContactRequest)
        .filter(
            (models.ContactRequest.sender_id == current_user.id)
            | (models.ContactRequest.recipient_id == current_user.id)
        )
        .order_by(models.ContactRequest.created_at.desc())
        .all()
    )
    return [_hydrate(db, r, current_user.id) for r in rows]


@router.patch("/{request_id}/respond", response_model=schemas.ContactRequestOut)
def respond_to_contact_request(
    request_id: str,
    payload: schemas.ContactRequestRespond,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """The recipient accepts or declines. Only on accept is private contact
    info revealed -- and only to these two users."""
    cr = db.query(models.ContactRequest).filter(models.ContactRequest.id == request_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Request not found")
    if cr.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recipient can respond to this request")

    cr.status = models.MessageStatus.accepted if payload.accept else models.MessageStatus.declined
    db.commit()
    db.refresh(cr)
    return _hydrate(db, cr, current_user.id)


def _hydrate(db: Session, cr: models.ContactRequest, viewer_id: str) -> schemas.ContactRequestOut:
    revealed = None
    if cr.status == models.MessageStatus.accepted and viewer_id in (cr.sender_id, cr.recipient_id):
        # Reveal the *recipient's* (report owner's) contact value to the sender,
        # and vice versa is intentionally NOT done automatically -- only the
        # original reporter's info is being requested here.
        recipient = db.query(models.User).filter(models.User.id == cr.recipient_id).first()
        if recipient:
            revealed = recipient.contact_value or "(no contact value on file)"
    return schemas.ContactRequestOut(
        id=cr.id, report_id=cr.report_id, match_id=cr.match_id,
        sender_id=cr.sender_id, recipient_id=cr.recipient_id,
        message_text=cr.message_text, status=cr.status,
        created_at=cr.created_at, revealed_contact=revealed,
    )
