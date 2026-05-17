"""
routers/tickets.py — Ticket CRUD endpoints with auth.
"""

from datetime import datetime, UTC
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.logger import get_logger
from api.models import Ticket, TicketEvent, TicketPriority, TicketStatus, TicketCategory, TicketSource, User
from api.schemas import TicketCreate, TicketUpdate, TicketOut

router = APIRouter(prefix="/tickets", tags=["Tickets"])
log = get_logger(__name__)


def _lookup(db, model, name, label):
    row = db.query(model).filter(model.name == name).first()
    if not row:
        valid = [r.name for r in db.query(model).all()]
        raise HTTPException(status_code=400, detail=f"Invalid {label} '{name}'. Valid values: {valid}")
    return row.id


def _log_event(db, ticket_id, event_type, message):
    db.add(TicketEvent(ticket_id=ticket_id, event_type=event_type, message=message))


@router.get("/", response_model=List[TicketOut], summary="List tickets")
def list_tickets(
    status:    Optional[str]  = Query(None),
    priority:  Optional[str]  = Query(None),
    category:  Optional[str]  = Query(None),
    assignee:  Optional[str]  = Query(None),
    escalated: Optional[bool] = Query(None),
    my_team:   Optional[bool] = Query(None, description="Filter tickets assigned to current user's team"),
    search:    Optional[str]  = Query(None, description="Search in title and description"),
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Ticket)

    if status:
        query = query.join(TicketStatus, Ticket.status_id == TicketStatus.id).filter(TicketStatus.name == status)
    if priority:
        query = query.join(TicketPriority, Ticket.priority_id == TicketPriority.id).filter(TicketPriority.name == priority)
    if category:
        query = query.join(TicketCategory, Ticket.category_id == TicketCategory.id).filter(TicketCategory.name == category)
    if assignee:
        query = query.filter(Ticket.assignee == assignee)
    if escalated is not None:
        query = query.filter(Ticket.escalated == escalated)
    if search:
        query = query.filter(
            Ticket.title.ilike(f"%{search}%") | Ticket.description.ilike(f"%{search}%")
        )
    # Filter by current user's team name
    if my_team and current_user.team_ref:
        team_name = current_user.team_ref.name
        query = query.filter(Ticket.assignee == team_name)

    results = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()
    return results


@router.get("/stats", summary="Ticket counts for dashboard")
def ticket_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns counts for the dashboard cards."""
    from sqlalchemy import func

    def count_by_status(status_name):
        return db.query(func.count(Ticket.id)).join(
            TicketStatus, Ticket.status_id == TicketStatus.id
        ).filter(TicketStatus.name == status_name).scalar() or 0

    return {
        "open":        count_by_status("open"),
        "in_progress": count_by_status("in_progress"),
        "escalated":   count_by_status("escalated"),
        "resolved":    count_by_status("resolved"),
        "sla_breached": db.query(func.count(Ticket.id)).filter(Ticket.sla_breached == True).scalar() or 0,
        "my_tickets":  db.query(func.count(Ticket.id)).filter(Ticket.assignee == current_user.username).scalar() or 0,
    }


@router.post("/", response_model=TicketOut, status_code=201, summary="Create a ticket")
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = Ticket(
        title       = payload.title,
        description = payload.description,
        assignee    = payload.assignee,
        reporter    = payload.reporter or current_user.username,
        priority_id = _lookup(db, TicketPriority, payload.priority, "priority"),
        status_id   = _lookup(db, TicketStatus,   "open",           "status"),
        category_id = _lookup(db, TicketCategory, payload.category, "category"),
        source_id   = _lookup(db, TicketSource,   payload.source,   "source"),
    )
    db.add(ticket)
    db.flush()
    _log_event(db, ticket.id, "created", f"Created by {current_user.username} via {payload.source}")
    db.commit()
    db.refresh(ticket)
    log.info("Ticket created", extra={"ticket_id": ticket.id, "user": current_user.username})
    return ticket


@router.get("/lookup-values", summary="Get valid values for all dropdowns")
def lookup_values(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns all valid dropdown values for the UI."""
    return {
        "priorities": [r.name for r in db.query(TicketPriority).all()],
        "statuses":   [r.name for r in db.query(TicketStatus).all()],
        "categories": [r.name for r in db.query(TicketCategory).all()],
        "sources":    [r.name for r in db.query(TicketSource).all()],
    }

@router.post("/{ticket_id}/events", status_code=201)
def add_ticket_event(
    ticket_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    event = TicketEvent(
        ticket_id  = ticket_id,
        event_type = body.get("event_type", "note"),
        message    = body.get("message", ""),
        author     = current_user.username
    )
    db.add(event); db.commit(); db.refresh(event)
    return event

@router.get("/{ticket_id}", response_model=TicketOut, summary="Get ticket detail")
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut, summary="Update a ticket")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    changes = payload.model_dump(exclude_unset=True)

    if "priority" in changes:
        ticket.priority_id = _lookup(db, TicketPriority, changes.pop("priority"), "priority")
    if "status" in changes:
        new_status = changes.pop("status")
        ticket.status_id = _lookup(db, TicketStatus, new_status, "status")
        if new_status == "resolved" and not ticket.resolved_at:
            ticket.resolved_at = datetime.now(UTC)
    if "category" in changes:
        ticket.category_id = _lookup(db, TicketCategory, changes.pop("category"), "category")
    if "source" in changes:
        ticket.source_id = _lookup(db, TicketSource, changes.pop("source"), "source")

    for field, value in changes.items():
        setattr(ticket, field, value)

    ticket.updated_at = datetime.now(UTC)
    _log_event(db, ticket.id, "updated", f"Updated by {current_user.username}: {', '.join(payload.model_dump(exclude_unset=True).keys())}")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204, summary="Delete a ticket")
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    db.delete(ticket)
    db.commit()
