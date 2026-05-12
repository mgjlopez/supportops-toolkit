"""
metrics.py — Custom Prometheus metrics for SupportOps.

Exposes business-level metrics by querying SQL Server:
  - supportops_tickets_total          (by status)
  - supportops_tickets_by_priority    (by priority)
  - supportops_tickets_by_category    (by category)
  - supportops_sla_breached_total     (count)
  - supportops_health_checks_total    (by check_type and status)

These are updated every time Prometheus scrapes /metrics.
"""

from prometheus_client import Gauge
from sqlalchemy import text

from api.database import SessionLocal

# ── Gauge definitions ─────────────────────────────────────────────────────────

tickets_by_status = Gauge(
    "supportops_tickets_total",
    "Number of tickets grouped by status",
    ["status"],
)

tickets_by_priority = Gauge(
    "supportops_tickets_by_priority",
    "Number of tickets grouped by priority",
    ["priority"],
)

tickets_by_category = Gauge(
    "supportops_tickets_by_category",
    "Number of tickets grouped by category",
    ["category"],
)

sla_breached_total = Gauge(
    "supportops_sla_breached_total",
    "Total number of tickets with SLA breached",
)

health_checks_by_type_status = Gauge(
    "supportops_health_checks_total",
    "Health check results grouped by type and status",
    ["check_type", "status"],
)


def collect_metrics():
    """
    Called on every Prometheus scrape. Queries SQL Server and updates all gauges.
    Runs inside a try/except so a DB error never breaks the /metrics endpoint.
    """
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT s.name AS status, COUNT(*) AS total
            FROM tickets t
            JOIN ticket_statuses s ON s.id = t.status_id
            GROUP BY s.name
        """)).mappings().all()
        for row in rows:
            tickets_by_status.labels(status=row["status"]).set(row["total"])

        rows = db.execute(text("""
            SELECT p.name AS priority, COUNT(*) AS total
            FROM tickets t
            JOIN ticket_priorities p ON p.id = t.priority_id
            GROUP BY p.name
        """)).mappings().all()
        for row in rows:
            tickets_by_priority.labels(priority=row["priority"]).set(row["total"])

        rows = db.execute(text("""
            SELECT c.name AS category, COUNT(*) AS total
            FROM tickets t
            JOIN ticket_categories c ON c.id = t.category_id
            GROUP BY c.name
        """)).mappings().all()
        for row in rows:
            tickets_by_category.labels(category=row["category"]).set(row["total"])

        row = db.execute(text("""
            SELECT COUNT(*) AS total FROM tickets WHERE sla_breached = 1
        """)).scalar()
        sla_breached_total.set(row or 0)

        rows = db.execute(text("""
            SELECT TOP 100 check_type, status, COUNT(*) AS total
            FROM health_checks
            GROUP BY check_type, status
        """)).mappings().all()
        for row in rows:
            health_checks_by_type_status.labels(
                check_type=row["check_type"],
                status=row["status"],
            ).set(row["total"])

    except Exception as e:
        print(f"[Metrics] Collection error: {e}")
    finally:
        db.close()
