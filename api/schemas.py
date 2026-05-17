"""
schemas.py — Pydantic models for API input/output.

TicketOut reads priority, status, category and source from the
nested relationship objects (_ref) using a validator so the API
still returns plain strings like "high", "open", etc.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


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
    author:     Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id:               int
    title:            str
    description:      Optional[str]
    assignee:         Optional[str]
    reporter:         Optional[str]
    escalated:        bool
    escalation_count: int
    sla_breached:     bool
    created_at:       datetime
    updated_at:       datetime
    resolved_at:      Optional[datetime]
    events:           List[TicketEventOut] = []

    # These are populated by the validator below from the _ref relationships
    priority: Optional[str] = None
    status:   Optional[str] = None
    category: Optional[str] = None
    source:   Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def resolve_lookup_names(cls, obj):
        """
        When building from an ORM Ticket object, read the names from
        the relationship objects instead of the raw FK integer columns.
        """
        if hasattr(obj, "priority_ref"):
            obj.__dict__["priority"] = obj.priority_ref.name if obj.priority_ref else None
            obj.__dict__["status"]   = obj.status_ref.name   if obj.status_ref   else None
            obj.__dict__["category"] = obj.category_ref.name if obj.category_ref else None
            obj.__dict__["source"]   = obj.source_ref.name   if obj.source_ref   else None
        return obj


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
    priority:             str
    avg_resolution_hours: Optional[float]
    min_resolution_hours: Optional[float]
    max_resolution_hours: Optional[float]


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
