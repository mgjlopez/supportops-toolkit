"""
routers/reports.py — Reporting endpoints backed by SQL Server queries.
Demonstrates real SQL skills: aggregation, DATEDIFF, GROUP BY, CTEs.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import get_db
from api.schemas import TicketSummary, SLAReport, ResolutionReport

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=List[TicketSummary], summary="Ticket volume by category")
def summary_report(db: Session = Depends(get_db)):
    """
    Returns ticket counts grouped by category.
    Useful for identifying which support areas generate the most load.
    """
    sql = text("""
        SELECT
            category,
            COUNT(*)                                        AS total,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END)       AS [open],
            SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END)    AS resolved,
            SUM(CASE WHEN escalated = 1 THEN 1 ELSE 0 END)          AS escalated
        FROM tickets
        GROUP BY category
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
            priority,
            COUNT(*)                                                AS total_tickets,
            SUM(CASE WHEN sla_breached = 1 THEN 1 ELSE 0 END)      AS breached,
            CAST(
                1.0 - (
                    SUM(CASE WHEN sla_breached = 1 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                )
            AS DECIMAL(5,4))                                        AS compliance_rate
        FROM tickets
        GROUP BY priority
        ORDER BY
            CASE priority
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
            priority,
            CAST(AVG(CAST(DATEDIFF(MINUTE, created_at, resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS avg_resolution_hours,
            CAST(MIN(CAST(DATEDIFF(MINUTE, created_at, resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS min_resolution_hours,
            CAST(MAX(CAST(DATEDIFF(MINUTE, created_at, resolved_at) AS FLOAT) / 60)
                AS DECIMAL(10,2))  AS max_resolution_hours
        FROM tickets
        WHERE resolved_at IS NOT NULL
        GROUP BY priority
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                WHEN 'low'      THEN 4
            END
    """)
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


@router.get("/health-checks", summary="Recent health check log")
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
