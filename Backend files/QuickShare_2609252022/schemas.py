from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import ReportKind, ReportStatus, MatchStatus, MessageStatus


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    contact_method: Optional[str] = "email"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: EmailStr
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Reports (Lost / Found)
# ---------------------------------------------------------------------------

class ReportBase(BaseModel):
    item_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    distinguishing_features: Optional[str] = None
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_time: Optional[datetime] = None
    contact_method: Optional[str] = "In-app message"


class ReportCreate(ReportBase):
    """Used for JSON-only creation; the router also accepts multipart with a photo."""
    pass


class ReportOut(ReportBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    kind: ReportKind
    status: ReportStatus
    photo_url: Optional[str] = None
    image_features: Optional[dict[str, Any]] = None
    is_flagged: bool
    created_at: datetime
    updated_at: datetime


class ReportStatusUpdate(BaseModel):
    status: ReportStatus


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

class MatchFactor(BaseModel):
    """One row of the transparent scoring breakdown shown in the UI."""
    factor: str
    label: str
    available: bool
    weight_base: float
    weight_effective: float
    score: Optional[float] = None  # 0-1, None if factor unavailable
    detail: Optional[str] = None


class MatchRequest(BaseModel):
    """POST /api/match body: run the matching engine for one report against
    all active reports of the opposite kind."""
    report_id: str


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lost_report_id: str
    found_report_id: str
    score: float
    factors: list[dict[str, Any]]
    reasons: list[str]
    status: MatchStatus
    created_at: datetime
    lost_report: Optional[ReportOut] = None
    found_report: Optional[ReportOut] = None


class MatchStatusUpdate(BaseModel):
    status: MatchStatus
    note: Optional[str] = None  # e.g. reason for flagging


# ---------------------------------------------------------------------------
# Contact requests / messages
# ---------------------------------------------------------------------------

class ContactRequestCreate(BaseModel):
    report_id: str
    match_id: Optional[str] = None
    message_text: Optional[str] = "Someone is interested in your item."


class ContactRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    report_id: str
    match_id: Optional[str] = None
    sender_id: str
    recipient_id: str
    message_text: Optional[str] = None
    status: MessageStatus
    created_at: datetime
    # Only populated once status == accepted, and only for the two participants
    revealed_contact: Optional[str] = None


class ContactRequestRespond(BaseModel):
    accept: bool


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

class ModerationTicketCreate(BaseModel):
    target_type: str
    target_id: str
    reason: str
    details: Optional[str] = None


class ModerationTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_type: str
    target_id: str
    reporter_id: Optional[str]
    reason: str
    details: Optional[str]
    status: str
    created_at: datetime


class ModerationDecision(BaseModel):
    status: str  # reviewed | dismissed
    action: Optional[str] = None  # e.g. "close_report", "remove_photo"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_lost: int
    total_found: int
    potential_matches: int
    matches_confirmed: int
    items_returned: int
    success_rate_pct: float
    activity_over_time: list[dict[str, Any]]
