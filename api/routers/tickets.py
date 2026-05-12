"""
routers/tickets.py — Ticket CRUD endpoints.
"""

from datetime import datetime, UTC
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.logger import get_logger
from api.models import Ticket, TicketEvent, TicketPriority, TicketStatus, TicketCategory, TicketSource
from api.schemas import TicketCreate, TicketUpdate, TicketOut

router = APIRouter(prefix="/tickets", tags=["Tickets"])
log = get_logger(__name__)


def _lookup(db: Session, model, name: str, field_label: str) -> int:
    row = db.query(model).filter(model.name == name).first()
    if not row:
        valid = [r.name for r in db.query(model).all()]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_label} '{name}'. Valid values: {valid}",
        )
    return row.id


def _log_event(db: Session, ticket_id: int, event_type: str, message: str):
    db.add(TicketEvent(ticket_id=ticket_id, event_type=event_type, message=message))


@router.get("/", response_model=List[TicketOut], summary="List tickets")
def list_tickets(
    status:    Optional[str]  = Query(None),
    priority:  Optional[str]  = Query(None),
    category:  Optional[str]  = Query(None),
    assignee:  Optional[str]  = Query(None),
    escalated: Optional[bool] = Query(None),
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket)
    if status:
        query = query.join(TicketStatus).filter(TicketStatus.name == status)
    if priority:
        query = query.join(TicketPriority).filter(TicketPriority.name == priority)
    if category:
        query = query.join(TicketCategory).filter(TicketCategory.name == category)
    if assignee:
        query = query.filter(Ticket.assignee == assignee)
    if escalated is not None:
        query = query.filter(Ticket.escalated == escalated)

    results = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()
    log.debug("Listed tickets", extra={"count": len(results), "filters": {
        "status": status, "priority": priority, "category": category,
    }})
    return results


@router.post("/", response_model=TicketOut, status_code=201, summary="Create a ticket")
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(
        title       = payload.title,
        description = payload.description,
        assignee    = payload.assignee,
        reporter    = payload.reporter,
        priority_id = _lookup(db, TicketPriority, payload.priority, "priority"),
        status_id   = _lookup(db, TicketStatus,   "open",           "status"),
        category_id = _lookup(db, TicketCategory, payload.category, "category"),
        source_id   = _lookup(db, TicketSource,   payload.source,   "source"),
    )
    db.add(ticket)
    db.flush()
    _log_event(db, ticket.id, "created", f"Ticket created via {payload.source}")
    db.commit()
    db.refresh(ticket)

    log.info("Ticket created", extra={
        "ticket_id": ticket.id,
        "priority":  payload.priority,
        "category":  payload.category,
        "source":    payload.source,
    })
    return ticket


@router.get("/{ticket_id}", response_model=TicketOut, summary="Get ticket detail")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        log.warning("Ticket not found", extra={"ticket_id": ticket_id})
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut, summary="Update a ticket")
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        log.warning("Ticket not found for update", extra={"ticket_id": ticket_id})
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
    _log_event(db, ticket.id, "updated", f"Fields updated: {', '.join(payload.model_dump(exclude_unset=True).keys())}")
    db.commit()
    db.refresh(ticket)

    log.info("Ticket updated", extra={"ticket_id": ticket_id, "changes": list(payload.model_dump(exclude_unset=True).keys())})
    return ticket


@router.delete("/{ticket_id}", status_code=204, summary="Delete a ticket")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        log.warning("Ticket not found for deletion", extra={"ticket_id": ticket_id})
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    db.delete(ticket)
    db.commit()
    log.info("Ticket deleted", extra={"ticket_id": ticket_id})
