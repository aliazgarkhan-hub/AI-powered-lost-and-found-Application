from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.matching.engine import compute_match, report_to_fields
from app.routers.reports_common import get_report_or_404

router = APIRouter(prefix="/api/match", tags=["matching"])
matches_router = APIRouter(prefix="/api/matches", tags=["matching"])

# Below this AI Match Score, we don't bother surfacing a suggested match --
# keeps the dashboard from filling up with noise.
MIN_SURFACE_SCORE = 20.0


def _upsert_match(db: Session, lost: models.Report, found: models.Report, result: dict) -> models.Match:
    existing = (
        db.query(models.Match)
        .filter(models.Match.lost_report_id == lost.id, models.Match.found_report_id == found.id)
        .first()
    )
    factors_json = [f for f in result["factors"]]
    if existing:
        existing.score = result["score"]
        existing.factors = factors_json
        existing.reasons = result["reasons"]
        db.commit()
        db.refresh(existing)
        return existing

    match = models.Match(
        lost_report_id=lost.id,
        found_report_id=found.id,
        score=result["score"],
        factors=factors_json,
        reasons=result["reasons"],
        status=models.MatchStatus.suggested,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.post("", response_model=list[schemas.MatchOut])
def run_match(
    payload: schemas.MatchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    POST /api/match
    ----------------
    This is THE agreed matching endpoint the frontend calls after a lost or
    found report is submitted (or whenever the user opens 'AI Matches').

    Body: {"report_id": "<id of a lost OR found report>"}

    Behavior: compares the given report against every ACTIVE report of the
    OPPOSITE kind, computes a transparent AI Match Score + factor breakdown
    for each pair using the real matching engine (no hard-coded results),
    stores/updates Match rows above a minimum threshold, and returns them
    sorted by score descending -- the agreed response shape.
    """
    source = get_report_or_404(db, payload.report_id)

    opposite_kind = models.ReportKind.found if source.kind == models.ReportKind.lost else models.ReportKind.lost
    candidates = (
        db.query(models.Report)
        .filter(models.Report.kind == opposite_kind)
        .filter(models.Report.status.in_([models.ReportStatus.active, models.ReportStatus.possible_match]))
        .all()
    )

    source_fields = report_to_fields(source)
    created_or_updated: list[models.Match] = []

    for candidate in candidates:
        candidate_fields = report_to_fields(candidate)
        if source.kind == models.ReportKind.lost:
            result = compute_match(source_fields, candidate_fields)
            lost_report, found_report = source, candidate
        else:
            result = compute_match(candidate_fields, source_fields)
            lost_report, found_report = candidate, source

        if result["score"] < MIN_SURFACE_SCORE:
            continue

        match = _upsert_match(db, lost_report, found_report, result)
        created_or_updated.append(match)

        # Mark both reports as having a possible match so they surface in dashboards
        for r in (lost_report, found_report):
            if r.status == models.ReportStatus.active:
                r.status = models.ReportStatus.possible_match
        db.commit()

    created_or_updated.sort(key=lambda m: m.score, reverse=True)
    return _hydrate_matches(created_or_updated)


def _hydrate_matches(matches: list[models.Match]) -> list[schemas.MatchOut]:
    out = []
    for m in matches:
        out.append(schemas.MatchOut(
            id=m.id, lost_report_id=m.lost_report_id, found_report_id=m.found_report_id,
            score=m.score, factors=m.factors, reasons=m.reasons, status=m.status,
            created_at=m.created_at,
            lost_report=schemas.ReportOut.model_validate(m.lost_report),
            found_report=schemas.ReportOut.model_validate(m.found_report),
        ))
    return out


@matches_router.get("", response_model=list[schemas.MatchOut])
def list_matches(
    status: Optional[models.MatchStatus] = None,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Match Dashboard feed: sorted by highest AI Match Score first."""
    q = db.query(models.Match)
    if status:
        q = q.filter(models.Match.status == status)
    if min_score is not None:
        q = q.filter(models.Match.score >= min_score)
    q = q.order_by(models.Match.score.desc())
    return _hydrate_matches(q.all())


@matches_router.get("/{match_id}", response_model=schemas.MatchOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return _hydrate_matches([match])[0]


@matches_router.patch("/{match_id}/status", response_model=schemas.MatchOut)
def update_match_status(
    match_id: str,
    payload: schemas.MatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Backs the dashboard buttons: Not a Match / Report Issue / Confirm."""
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    match.status = payload.status
    if payload.status == models.MatchStatus.confirmed:
        match.lost_report.status = models.ReportStatus.match_confirmed
        match.found_report.status = models.ReportStatus.match_confirmed
    elif payload.status == models.MatchStatus.rejected:
        # Revert reports to active if they have no other pending matches
        for r in (match.lost_report, match.found_report):
            other_pending = (
                db.query(models.Match)
                .filter(
                    ((models.Match.lost_report_id == r.id) | (models.Match.found_report_id == r.id)),
                    models.Match.id != match.id,
                    models.Match.status == models.MatchStatus.suggested,
                )
                .first()
            )
            if not other_pending and r.status == models.ReportStatus.possible_match:
                r.status = models.ReportStatus.active
    elif payload.status == models.MatchStatus.flagged:
        ticket = models.ModerationTicket(
            target_type=models.ModerationTargetType.match,
            target_id=match.id,
            reporter_id=current_user.id,
            reason="report_issue",
            details=payload.note,
        )
        db.add(ticket)

    db.commit()
    db.refresh(match)
    return _hydrate_matches([match])[0]
