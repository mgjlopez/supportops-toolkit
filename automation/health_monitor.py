"""
health_monitor.py — Automated health checker with structured logging.
"""

import os
import sys
import httpx
import psutil
from datetime import datetime, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.logger import get_logger
from automation.slack_notifier import notify_new_ticket

log = get_logger(__name__)

API_BASE        = os.getenv("API_BASE_URL", "http://api:8000")
MONITOR_URLS    = [u.strip() for u in os.getenv("MONITOR_URLS", "http://api:8000/health").split(",") if u.strip()]
DISK_THRESHOLD  = float(os.getenv("DISK_THRESHOLD_PERCENT", "85"))
CPU_THRESHOLD   = float(os.getenv("CPU_THRESHOLD_PERCENT",  "90"))
RAM_THRESHOLD   = float(os.getenv("RAM_THRESHOLD_PERCENT",  "90"))

_active_incidents: dict[tuple, int] = {}


def _create_ticket(title: str, description: str, priority: str, category: str) -> int | None:
    try:
        resp = httpx.post(f"{API_BASE}/tickets", json={
            "title":       title,
            "description": description,
            "priority":    priority,
            "category":    category,
            "source":      "auto",
            "reporter":    "health_monitor",
        }, timeout=10)
        if resp.status_code == 201:
            ticket = resp.json()
            tid = ticket["id"]
            log.info("Auto-ticket created", extra={"ticket_id": tid, "title": title})
            notify_new_ticket(
                ticket_id = tid,
                title     = title,
                priority  = priority,
                category  = category,
                assignee  = ticket.get("assignee"),
            )
            return tid
        log.warning("Ticket creation failed", extra={"status_code": resp.status_code})
    except Exception as e:
        log.error("Ticket creation error", extra={"error": str(e)})
    return None


def _log_health_check(target, check_type, status, value, message, ticket_id=None):
    try:
        httpx.post(f"{API_BASE}/health-checks", json={
            "target": target, "check_type": check_type,
            "status": status, "value": value,
            "message": message, "ticket_id": ticket_id,
        }, timeout=5)
    except Exception:
        pass


def check_http_endpoints():
    for url in MONITOR_URLS:
        key = ("http", url)
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            if resp.status_code < 400:
                log.info("HTTP check OK", extra={"url": url, "status_code": resp.status_code})
                _log_health_check(url, "http", "ok", resp.status_code, f"HTTP {resp.status_code} OK")
                _active_incidents.pop(key, None)
            else:
                raise ValueError(f"HTTP {resp.status_code}")
        except Exception as e:
            msg = f"HTTP check failed for {url}: {e}"
            log.warning("HTTP check failed", extra={"url": url, "error": str(e)})
            if key not in _active_incidents:
                tid = _create_ticket(
                    title=f"HTTP endpoint down: {url}",
                    description=f"{msg}\nTime: {datetime.now(UTC).isoformat()}",
                    priority="high", category="network",
                )
                if tid:
                    _active_incidents[key] = tid
            _log_health_check(url, "http", "critical", None, msg, _active_incidents.get(key))


def check_disk_usage():
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            pct   = usage.percent
            key   = ("disk", partition.mountpoint)
            if pct >= DISK_THRESHOLD:
                status = "critical" if pct >= 95 else "warning"
                msg    = f"Disk {partition.mountpoint} at {pct:.1f}% — threshold {DISK_THRESHOLD}%"
                log.warning("Disk threshold exceeded", extra={"mount": partition.mountpoint, "usage_pct": pct})
                if key not in _active_incidents:
                    tid = _create_ticket(
                        title=f"Disk usage alert: {partition.mountpoint} at {pct:.1f}%",
                        description=f"{msg}\nFree: {usage.free // (1024**3)} GB",
                        priority="critical" if pct >= 95 else "high", category="performance",
                    )
                    if tid:
                        _active_incidents[key] = tid
                _log_health_check(partition.mountpoint, "disk", status, pct, msg, _active_incidents.get(key))
            else:
                log.info("Disk check OK", extra={"mount": partition.mountpoint, "usage_pct": pct})
                _log_health_check(partition.mountpoint, "disk", "ok", pct, f"Disk at {pct:.1f}%")
                _active_incidents.pop(key, None)
        except PermissionError:
            continue


def check_cpu_usage():
    pct = psutil.cpu_percent(interval=1)
    key = ("cpu", "local")
    if pct >= CPU_THRESHOLD:
        log.warning("CPU threshold exceeded", extra={"cpu_pct": pct})
        if key not in _active_incidents:
            tid = _create_ticket(
                title=f"High CPU usage detected: {pct:.1f}%",
                description=f"CPU at {pct:.1f}% — threshold {CPU_THRESHOLD}%",
                priority="critical" if pct >= 95 else "high", category="performance",
            )
            if tid:
                _active_incidents[key] = tid
        _log_health_check("local", "cpu", "critical", pct, f"CPU at {pct:.1f}%", _active_incidents.get(key))
    else:
        log.info("CPU check OK", extra={"cpu_pct": pct})
        _log_health_check("local", "cpu", "ok", pct, f"CPU at {pct:.1f}%")
        _active_incidents.pop(key, None)


def check_ram_usage():
    mem = psutil.virtual_memory()
    pct = mem.percent
    key = ("ram", "local")
    if pct >= RAM_THRESHOLD:
        log.warning("RAM threshold exceeded", extra={"ram_pct": pct})
        if key not in _active_incidents:
            tid = _create_ticket(
                title=f"High RAM usage detected: {pct:.1f}%",
                description=f"RAM at {pct:.1f}% — threshold {RAM_THRESHOLD}%\nAvailable: {mem.available // (1024**2)} MB",
                priority="high", category="performance",
            )
            if tid:
                _active_incidents[key] = tid
        _log_health_check("local", "ram", "critical", pct, f"RAM at {pct:.1f}%", _active_incidents.get(key))
    else:
        log.info("RAM check OK", extra={"ram_pct": pct})
        _log_health_check("local", "ram", "ok", pct, f"RAM at {pct:.1f}%")
        _active_incidents.pop(key, None)


def run_all_checks():
    log.info("Health check cycle started")
    check_http_endpoints()
    check_disk_usage()
    check_cpu_usage()
    check_ram_usage()
    log.info("Health check cycle complete")


if __name__ == "__main__":
    run_all_checks()
