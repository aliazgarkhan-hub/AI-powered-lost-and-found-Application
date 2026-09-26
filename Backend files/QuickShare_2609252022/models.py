import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Float, DateTime, ForeignKey, Enum as SAEnum, Boolean, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReportKind(str, enum.Enum):
    lost = "lost"
    found = "found"


class ReportStatus(str, enum.Enum):
    active = "active"
    possible_match = "possible_match"
    match_confirmed = "match_confirmed"
    returned = "returned"
    closed = "closed"


class MatchStatus(str, enum.Enum):
    suggested = "suggested"
    confirmed = "confirmed"
    rejected = "rejected"          # "Not a Match"
    flagged = "flagged"            # "Report Issue"


class MessageStatus(str, enum.Enum):
    pending = "pending"       # waiting for recipient to accept/decline
    accepted = "accepted"     # contact info revealed
    declined = "declined"


class ModerationTargetType(str, enum.Enum):
    report = "report"
    match = "match"
    message = "message"


class ModerationStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    dismissed = "dismissed"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    contact_method = Column(String, nullable=True)  # e.g. "email" / "phone" -- never shown publicly
    contact_value = Column(String, nullable=True)   # actual private value, only revealed on accepted contact
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_utc)

    reports = relationship("Report", back_populates="owner")


# ---------------------------------------------------------------------------
# Report (covers both Lost and Found; `kind` distinguishes them)
# ---------------------------------------------------------------------------

class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=gen_id)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)

    kind = Column(SAEnum(ReportKind), nullable=False, index=True)
    status = Column(SAEnum(ReportStatus), default=ReportStatus.active, index=True)

    item_name = Column(String, nullable=False)
    category = Column(String, nullable=True, index=True)     # e.g. laptop, phone, wallet, keys
    description = Column(Text, nullable=True)
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)
    color = Column(String, nullable=True)
    distinguishing_features = Column(Text, nullable=True)

    location_text = Column(String, nullable=True)   # approximate / human-readable, never exact address
    latitude = Column(Float, nullable=True)          # optional, approximate (rounded) coordinates
    longitude = Column(Float, nullable=True)

    event_time = Column(DateTime, nullable=True)     # date/time lost or found

    photo_url = Column(String, nullable=True)
    image_features = Column(JSON, nullable=True)     # output of the image analysis abstraction layer

    contact_method = Column(String, nullable=True)   # display-only label e.g. "In-app message"

    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    owner = relationship("User", back_populates="reports")


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=gen_id)
    lost_report_id = Column(String, ForeignKey("reports.id"), nullable=False, index=True)
    found_report_id = Column(String, ForeignKey("reports.id"), nullable=False, index=True)

    score = Column(Float, nullable=False)                 # 0-100, the "AI Match Score"
    factors = Column(JSON, nullable=False)                 # transparent per-factor breakdown
    reasons = Column(JSON, nullable=False)                 # human-readable "why this may match" bullets

    status = Column(SAEnum(MatchStatus), default=MatchStatus.suggested, index=True)

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    lost_report = relationship("Report", foreign_keys=[lost_report_id])
    found_report = relationship("Report", foreign_keys=[found_report_id])


# ---------------------------------------------------------------------------
# Messages / in-app contact requests
# ---------------------------------------------------------------------------

class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id = Column(String, primary_key=True, default=gen_id)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    match_id = Column(String, ForeignKey("matches.id"), nullable=True)

    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=False)

    message_text = Column(Text, nullable=True)
    status = Column(SAEnum(MessageStatus), default=MessageStatus.pending)

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

class ModerationTicket(Base):
    __tablename__ = "moderation_tickets"

    id = Column(String, primary_key=True, default=gen_id)
    target_type = Column(SAEnum(ModerationTargetType), nullable=False)
    target_id = Column(String, nullable=False)
    reporter_id = Column(String, ForeignKey("users.id"), nullable=True)
    reason = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    status = Column(SAEnum(ModerationStatus), default=ModerationStatus.open, index=True)
    created_at = Column(DateTime, default=now_utc)
