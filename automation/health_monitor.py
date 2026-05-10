"""
health_monitor.py — Automated health checker.

Runs on a schedule and checks:
  - HTTP endpoints (configurable via MONITOR_URLS env var)
  - Local disk usage
  - Local CPU usage
  - Local RAM usage

When a check fails, it automatically creates a ticket via the REST API
(so you can see auto-ticketing in action end-to-end).
"""

import os
import httpx
import psutil
import socket
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HealthMonitor] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
MONITOR_URLS = [
    u.strip()
    for u in os.getenv("MONITOR_URLS", "http://api:8000/health").split(",")
    if u.strip()
]
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD_PERCENT", "85"))
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD_PERCENT", "90"))
RAM_THRESHOLD = float(os.getenv("RAM_THRESHOLD_PERCENT", "90"))

# Maps (check_type, target) → ticket_id to avoid duplicate tickets per session
_active_incidents: dict[tuple, int] = {}


def _create_ticket(title: str, description: str, priority: str, category: str) -> int | None:
    """Creates a ticket via the REST API. Returns the ticket ID or None on failure."""
    try:
        resp = httpx.post(
            f"{API_BASE}/tickets",
            json={
                "title": title,
                "description": description,
                "priority": priority,
                "category": category,
                "source": "auto",
                "reporter": "health_monitor",
            },
            timeout=10,
        )
        if resp.status_code == 201:
            tid = resp.json()["id"]
            log.info(f"🎫 Auto-created ticket #{tid}: {title}")
            return tid
        else:
            log.warning(f"Ticket creation returned {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"Failed to create ticket: {e}")
    return None


def _log_health_check(
    target: str,
    check_type: str,
    status: str,
    value: float | None,
    message: str,
    ticket_id: int | None = None,
):
    """Persists health check result to SQL Server via the API."""
    try:
        httpx.post(
            f"{API_BASE}/health-checks",
            json={
                "target": target,
                "check_type": check_type,
                "status": status,
                "value": value,
                "message": message,
                "ticket_id": ticket_id,
            },
            timeout=5,
        )
    except Exception:
        pass  # Logging failure shouldn't stop the monitor


def check_http_endpoints():
    """Checks each URL in MONITOR_URLS. Creates a ticket if unreachable."""
    for url in MONITOR_URLS:
        key = ("http", url)
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            if resp.status_code < 400:
                log.info(f"✅ HTTP OK: {url} ({resp.status_code})")
                _log_health_check(url, "http", "ok", resp.status_code, f"HTTP {resp.status_code} OK")
                _active_incidents.pop(key, None)
            else:
                raise ValueError(f"HTTP {resp.status_code}")
        except Exception as e:
            msg = f"HTTP check failed for {url}: {e}"
            log.warning(f"⚠️  {msg}")

            if key not in _active_incidents:
                tid = _create_ticket(
                    title=f"HTTP endpoint down: {url}",
                    description=f"Health monitor detected: {msg}\nTime: {datetime.utcnow().isoformat()}",
                    priority="high",
                    category="network",
                )
                if tid:
                    _active_incidents[key] = tid
            _log_health_check(url, "http", "critical", None, msg, _active_incidents.get(key))


def check_disk_usage():
    """Checks disk usage on all partitions. Tickets on threshold breach."""
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            pct = usage.percent
            key = ("disk", partition.mountpoint)
            status = "ok"

            if pct >= DISK_THRESHOLD:
                status = "critical" if pct >= 95 else "warning"
                msg = f"Disk {partition.mountpoint} at {pct:.1f}% — threshold {DISK_THRESHOLD}%"
                log.warning(f"⚠️  {msg}")

                if key not in _active_incidents:
                    priority = "critical" if pct >= 95 else "high"
                    tid = _create_ticket(
                        title=f"Disk usage alert: {partition.mountpoint} at {pct:.1f}%",
                        description=f"{msg}\nFree: {usage.free // (1024**3)} GB",
                        priority=priority,
                        category="performance",
                    )
                    if tid:
                        _active_incidents[key] = tid
                _log_health_check(partition.mountpoint, "disk", status, pct, msg, _active_incidents.get(key))
            else:
                log.info(f"✅ Disk OK: {partition.mountpoint} at {pct:.1f}%")
                _log_health_check(partition.mountpoint, "disk", "ok", pct, f"Disk at {pct:.1f}%")
                _active_incidents.pop(key, None)

        except PermissionError:
            continue


def check_cpu_usage():
    """Checks CPU usage (1-second sample). Tickets on sustained high usage."""
    pct = psutil.cpu_percent(interval=1)
    key = ("cpu", "local")

    if pct >= CPU_THRESHOLD:
        msg = f"CPU at {pct:.1f}% — threshold {CPU_THRESHOLD}%"
        log.warning(f"⚠️  {msg}")

        if key not in _active_incidents:
            tid = _create_ticket(
                title=f"High CPU usage detected: {pct:.1f}%",
                description=f"{msg}\nTime: {datetime.utcnow().isoformat()}",
                priority="critical" if pct >= 95 else "high",
                category="performance",
            )
            if tid:
                _active_incidents[key] = tid
        _log_health_check("local", "cpu", "critical", pct, msg, _active_incidents.get(key))
    else:
        log.info(f"✅ CPU OK: {pct:.1f}%")
        _log_health_check("local", "cpu", "ok", pct, f"CPU at {pct:.1f}%")
        _active_incidents.pop(key, None)


def check_ram_usage():
    """Checks RAM usage. Tickets on threshold breach."""
    mem = psutil.virtual_memory()
    pct = mem.percent
    key = ("ram", "local")

    if pct >= RAM_THRESHOLD:
        msg = f"RAM at {pct:.1f}% — threshold {RAM_THRESHOLD}%"
        log.warning(f"⚠️  {msg}")

        if key not in _active_incidents:
            tid = _create_ticket(
                title=f"High RAM usage detected: {pct:.1f}%",
                description=f"{msg}\nAvailable: {mem.available // (1024**2)} MB",
                priority="high",
                category="performance",
            )
            if tid:
                _active_incidents[key] = tid
        _log_health_check("local", "ram", "critical", pct, msg, _active_incidents.get(key))
    else:
        log.info(f"✅ RAM OK: {pct:.1f}%")
        _log_health_check("local", "ram", "ok", pct, f"RAM at {pct:.1f}%")
        _active_incidents.pop(key, None)


def run_all_checks():
    """Runs all health checks in sequence."""
    log.info("--- Running health checks ---")
    check_http_endpoints()
    check_disk_usage()
    check_cpu_usage()
    check_ram_usage()
    log.info("--- Health check cycle complete ---")


if __name__ == "__main__":
    run_all_checks()
