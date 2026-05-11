"""
schemas.py — Pydantic models for API input validation and response serialization.

Priority, status, category and source are still plain strings in the API
contract — the router resolves them to lookup IDs internally.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Ticket Schemas ────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title:       str            = Field(..., min_length=5, max_length=255)
    description: Optional[str] = None
    priority:    str            = "medium"
    category:    str            = "other"
    assignee:    Optional[str] = None
    reporter:    Optional[str] = None
    source:      str            = "manual"


class TicketUpdate(BaseModel):
    title:       Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = None
    priority:    Optional[str] = None
    status:      Optional[str] = None
    category:    Optional[str] = None
    assignee:    Optional[str] = None
    resolved_at: Optional[datetime] = None


class TicketEventOut(BaseModel):
    id:         int
    event_type: str
    message:    Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id:               int
    title:            str
    description:      Optional[str]
    priority:         Optional[str]
    status:           Optional[str]
    category:         Optional[str]
    assignee:         Optional[str]
    reporter:         Optional[str]
    source:           Optional[str]
    escalated:        bool
    escalation_count: int
    sla_breached:     bool
    created_at:       datetime
    updated_at:       datetime
    resolved_at:      Optional[datetime]
    events:           List[TicketEventOut] = []

    model_config = {"from_attributes": True}


# ── Report Schemas ────────────────────────────────────────────────────────────

class TicketSummary(BaseModel):
    category:  str
    total:     int
    open:      int
    resolved:  int
    escalated: int


class SLAReport(BaseModel):
    priority:        str
    total_tickets:   int
    breached:        int
    compliance_rate: float


class ResolutionReport(BaseModel):
    priority:              str
    avg_resolution_hours:  Optional[float]
    min_resolution_hours:  Optional[float]
    max_resolution_hours:  Optional[float]


# ── Health Check Schemas ──────────────────────────────────────────────────────

class HealthCheckOut(BaseModel):
    id:         int
    target:     str
    check_type: str
    status:     str
    value:      Optional[float]
    message:    Optional[str]
    ticket_id:  Optional[int]
    checked_at: datetime

    model_config = {"from_attributes": True}
