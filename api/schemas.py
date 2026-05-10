"""
schemas.py — Pydantic models for API input validation and response serialization.
Keeps API contracts separate from the database ORM models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from api.models import Priority, TicketStatus, TicketCategory


# ── Ticket Schemas ──────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255, examples=["VPN not connecting for remote user"])
    description: Optional[str] = Field(None, examples=["User reports VPN client fails at auth step since yesterday"])
    priority: Priority = Priority.MEDIUM
    category: TicketCategory = TicketCategory.OTHER
    assignee: Optional[str] = Field(None, examples=["john.doe"])
    reporter: Optional[str] = Field(None, examples=["jane.smith"])
    source: str = "manual"


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[TicketStatus] = None
    category: Optional[TicketCategory] = None
    assignee: Optional[str] = None
    resolved_at: Optional[datetime] = None


class TicketEventOut(BaseModel):
    id: int
    event_type: str
    message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    status: str
    category: str
    assignee: Optional[str]
    reporter: Optional[str]
    source: str
    escalated: bool
    escalation_count: int
    sla_breached: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    events: List[TicketEventOut] = []

    model_config = {"from_attributes": True}


# ── Report Schemas ───────────────────────────────────────────────────────────

class TicketSummary(BaseModel):
    category: str
    total: int
    open: int
    resolved: int
    escalated: int


class SLAReport(BaseModel):
    priority: str
    total_tickets: int
    breached: int
    compliance_rate: float  # 0.0 to 1.0


class ResolutionReport(BaseModel):
    priority: str
    avg_resolution_hours: Optional[float]
    min_resolution_hours: Optional[float]
    max_resolution_hours: Optional[float]


# ── Health Check Schemas ─────────────────────────────────────────────────────

class HealthCheckOut(BaseModel):
    id: int
    target: str
    check_type: str
    status: str
    value: Optional[float]
    message: Optional[str]
    ticket_id: Optional[int]
    checked_at: datetime

    model_config = {"from_attributes": True}
