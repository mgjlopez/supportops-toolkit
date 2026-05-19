"""
routers/reports.py — Reporting endpoints backed by SQL Server queries.
Demonstrates real SQL skills: aggregation, DATEDIFF, GROUP BY, CTEs.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.schemas import ResolutionReport, SLAReport, TicketSummary

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=List[TicketSummary], summary="Ticket volume by category")
def summary_report(db: Session = Depends(get_db)):
    """
    Returns ticket counts grouped by category.
    Useful for identifying which support areas generate the most load.
    """
    sql = text("""
        SELECT
            c.name AS category,
            COUNT(*)                                               AS total,
            SUM(CASE WHEN s.name = 'open' THEN 1 ELSE 0 END)       AS [open],
            SUM(CASE WHEN s.name = 'resolved' THEN 1 ELSE 0 END)   AS resolved,
            SUM(CASE WHEN t.escalated = 1 THEN 1 ELSE 0 END)       AS escalated
        FROM tickets t
        JOIN ticket_categories c ON c.id = t.category_id
        JOIN ticket_statuses   s ON s.id = t.status_id
        GROUP BY c.name
        ORDER BY total DESC
    """)
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


@router.get("/sla", response_model=List[SLAReport], summary="SLA compliance by priority")
def sla_report(db: Session = Depends(get_db)):
    """
    Calculates SLA compliance rate per priority level.
    sla_breached = 1 means the ticket exceeded its allowed response/resolution window.
    """
    sql = text("""
        SELECT
            p.name AS priority,
            COUNT(*)                                                AS total_tickets,
            SUM(CASE WHEN t.sla_breached = 1 THEN 1 ELSE 0 END)     AS breached,
            CAST(
                1.0 - (
                    SUM(CASE WHEN t.sla_breached = 1 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                )
            AS DECIMAL(5,4))                                        AS compliance_rate
        FROM tickets t
        JOIN ticket_priorities p ON p.id = t.priority_id
        GROUP BY p.name
        ORDER BY
            CASE p.name
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                WHEN 'low'      THEN 4
            END
    """)
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


@router.get("/resolution", response_model=List[ResolutionReport], summary="Avg resolution time")
def resolution_report(db: Session = Depends(get_db)):
    """
    Average, min, and max resolution time in hours, grouped by priority.
    Only considers tickets that have been resolved (resolved_at IS NOT NULL).
    """
    sql = text("""
        SELECT
            p.name AS priority,
            CAST(AVG(CAST(DATEDIFF(MINUTE, t.created_at, t.resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS avg_resolution_hours,
            CAST(MIN(CAST(DATEDIFF(MINUTE, t.created_at, t.resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS min_resolution_hours,
            CAST(MAX(CAST(DATEDIFF(MINUTE, t.created_at, t.resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS max_resolution_hours
        FROM tickets t
        JOIN ticket_priorities p ON p.id = t.priority_id
        WHERE t.resolved_at IS NOT NULL
        GROUP BY p.name
        ORDER BY
            CASE p.name
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                WHEN 'low'      THEN 4
            END
    """)
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


@router.get("/trend", summary="Ticket volume by day (last N days)")
def trend_report(days: int = 7, db: Session = Depends(get_db)):
    """
    Returns daily ticket creation counts for the last N days.
    Used to render the volume trend chart in the dashboard.
    """
    sql = text("""
        SELECT
            CAST(t.created_at AS DATE)  AS day,
            COUNT(*)                    AS total,
            SUM(CASE WHEN s.name IN ('open','in_progress','escalated') THEN 1 ELSE 0 END) AS open,
            SUM(CASE WHEN s.name IN ('resolved','closed')              THEN 1 ELSE 0 END) AS resolved
        FROM tickets t
        JOIN ticket_statuses s ON s.id = t.status_id
        WHERE t.created_at >= DATEADD(DAY, -:days, GETUTCDATE())
        GROUP BY CAST(t.created_at AS DATE)
        ORDER BY day ASC
    """)
    rows = db.execute(sql, {"days": days}).mappings().all()
    return [{"day": str(r["day"]), "total": r["total"], "open": r["open"], "resolved": r["resolved"]} for r in rows]

def health_checks_report(limit: int = 50, db: Session = Depends(get_db)):
    """Returns the most recent health check results from the monitor."""
    sql = text("""
        SELECT TOP (:limit)
            target, check_type, status, value, message, ticket_id, checked_at
        FROM health_checks
        ORDER BY checked_at DESC
    """)
    rows = db.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]
