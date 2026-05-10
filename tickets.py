"""
routers/tickets.py — Ticket management endpoints.
Covers the full lifecycle: create, read, update, close, and audit trail.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Ticket, TicketEvent, TicketStatus
from api.schemas import TicketCreate, TicketUpdate, TicketOut

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _log_event(db: Session, ticket_id: int, event_type: str, message: str):
    event = TicketEvent(ticket_id=ticket_id, event_type=event_type, message=message)
    db.add(event)


@router.get("/", response_model=List[TicketOut], summary="List tickets")
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    escalated: Optional[bool] = Query(None, description="Filter escalated tickets"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if category:
        query = query.filter(Ticket.category == category)
    if assignee:
        query = query.filter(Ticket.assignee == assignee)
    if escalated is not None:
        query = query.filter(Ticket.escalated == escalated)
    return query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/", response_model=TicketOut, status_code=201, summary="Create a ticket")
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(**payload.model_dump())
    db.add(ticket)
    db.flush()  # get the ID before committing
    _log_event(db, ticket.id, "created", f"Ticket created via {payload.source}")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketOut, summary="Get ticket detail")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut, summary="Update a ticket")
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    changes = payload.model_dump(exclude_unset=True)

    # Auto-set resolved_at when status changes to resolved
    if changes.get("status") == TicketStatus.RESOLVED and not ticket.resolved_at:
        changes["resolved_at"] = datetime.utcnow()

    for field, value in changes.items():
        setattr(ticket, field, value)

    ticket.updated_at = datetime.utcnow()
    _log_event(db, ticket.id, "updated", f"Fields updated: {', '.join(changes.keys())}")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204, summary="Delete a ticket")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    db.delete(ticket)
    db.commit()
