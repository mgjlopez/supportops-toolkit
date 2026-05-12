# 🛠️ SupportOps Toolkit

![CI](https://github.com/mgjlopez/supportops-toolkit/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python)
![SQL Server](https://img.shields.io/badge/SQL_Server-2025-red?logo=microsoftsqlserver)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/license-MIT-green)

> A production-style IT support automation system built with Python, FastAPI, SQL Server, Docker, and Grafana.  
> Simulates real-world workflows: auto-ticketing, SLA escalation, health monitoring, and observability dashboards.

---

## 📌 What This Project Does

SupportOps Toolkit automates the repetitive work of a Technical Support Engineer:

| Module | Description |
|---|---|
| 🔍 **Health Monitor** | Polls system/service health and logs metrics to SQL Server |
| 🎫 **Auto-Ticketing** | Detects incidents and opens tickets automatically |
| ⏫ **Escalation Engine** | Escalates tickets that breach SLA thresholds |
| 🌐 **REST API** | FastAPI interface to manage tickets (like a mini Ticketing System) |
| 📊 **Reports** | SQL-based reports: resolution time, ticket volume, SLA compliance |
| 📈 **Observability** | Prometheus + Grafana dashboard with live ticket and health check metrics |

Everything runs locally via **Docker Compose** — no paid cloud services needed.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Network                            │
│                                                                  │
│  ┌─────────────┐      ┌──────────────────────┐                   │
│  │  SQL Server │◄─────│   FastAPI (port 8000) │                  │
│  │    2025     │      │   REST API + Logic    │                  │
│  │  port 1433  │      └──────────┬────────────┘                  │
│  └─────────────┘                 │                               │
│                         ┌────────▼────────┐                      │
│                         │  Python Scripts │                      │
│                         │  (schedulers)   │                      │
│                         └────────┬────────┘                      │
│                                  │ /metrics                      │
│                         ┌────────▼────────┐    ┌─────────────┐   │
│                         │   Prometheus    │───►│   Grafana   │   │
│                         │   port 9090     │    │  port 3000  │   │
│                         └─────────────────┘    └─────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.10+ (for running scripts outside Docker)

### 1. Clone and start

```bash
git clone https://github.com/mgjlopez/supportops-toolkit.git
cd supportops-toolkit
cp .env.example .env
docker compose up -d
```

### 2. Wait ~30 seconds for SQL Server to initialize, then run migrations

```bash
docker compose exec api python db/migrate.py
```

### 3. Seed sample data (optional)

```bash
docker compose exec api python db/seed.py
```

### 4. Access the services

| Service | URL | Credentials |
|---|---|---|
| **API Swagger UI** | http://localhost:8000/docs | — |
| **API Health check** | http://localhost:8000/health | — |
| **Prometheus** | http://localhost:9090 | — |
| **Grafana** | http://localhost:3000 | admin / (set in `.env`) |

---

## 📁 Project Structure

```
supportops-toolkit/
├── api/                        # FastAPI application
│   ├── main.py                 # App entrypoint + routes
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic request/response models
│   ├── database.py             # SQLAlchemy + SQL Server connection
│   ├── metrics.py              # Custom Prometheus metrics
│   └── routers/
│       ├── tickets.py          # Ticket CRUD endpoints
│       └── reports.py          # Reporting endpoints
├── automation/                 # Core automation scripts
│   ├── health_monitor.py       # System health checks → auto-tickets
│   ├── escalation_engine.py    # SLA breach detection + escalation
│   └── scheduler.py            # Runs monitor + escalation on a schedule
├── monitoring/                 # Observability configuration
│   ├── prometheus.yml          # Prometheus scrape config
│   └── grafana/
│       ├── datasources/        # Auto-configured Prometheus datasource
│       └── dashboards/         # Pre-built SupportOps dashboard
├── db/
│   ├── migrate.py              # Schema creation + lookup table seeding
│   └── seed.py                 # Sample data loader
├── docs/
│   └── runbook.md              # Incident response runbook
├── tests/
│   └── test_tickets.py        # API endpoint tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 🔧 Key Features Explained

### Health Monitor
Runs on a schedule (every 60s). Checks:
- HTTP endpoints (configurable list)
- Port availability (TCP check)
- Disk usage thresholds
- CPU/RAM thresholds

When a check fails, it automatically creates a ticket with severity based on the failure type.

### Escalation Engine
Reads open tickets and checks age vs. SLA rules:

| Priority | Response SLA | Resolution SLA |
|---|---|---|
| Critical | 15 min | 1 hour |
| High | 1 hour | 4 hours |
| Medium | 4 hours | 24 hours |
| Low | 24 hours | 72 hours |

Breached tickets get escalated and flagged in the database.

### REST API Endpoints

```
GET    /tickets              List all tickets (filterable by status, priority, category)
POST   /tickets              Create a ticket manually
GET    /tickets/{id}         Get ticket detail with full audit trail
PATCH  /tickets/{id}         Update status/assignee/priority
DELETE /tickets/{id}         Delete a ticket

GET    /reports/summary      Ticket volume by category
GET    /reports/sla          SLA compliance rate by priority
GET    /reports/resolution   Average resolution time by priority
GET    /health               Service health check
GET    /metrics              Prometheus metrics endpoint
```

### Observability — Prometheus + Grafana

The API exposes a `/metrics` endpoint that Prometheus scrapes every 15 seconds. Grafana reads from Prometheus and displays a pre-built dashboard with:

- **Open / Escalated / SLA-breached ticket counts** — color-coded stat panels
- **Tickets by priority** — donut chart
- **Tickets by category** — donut chart
- **Ticket volume over time** — time series
- **Health check results over time** — time series by check type

The dashboard is provisioned automatically on startup — no manual setup needed.

### Normalized Database Schema

Priority, status, category and source values are stored in their own lookup tables with foreign keys, enforcing valid values at the database level. Invalid values return a descriptive `400` error.

```
ticket_priorities ──┐
ticket_statuses   ──┤──► tickets ──► ticket_events
ticket_categories ──┤
ticket_sources    ──┘
```

---

## 🧪 Running Tests

```bash
docker compose exec api pytest tests/ -v
```

Tests use an in-memory SQLite database — no SQL Server required to run them.

---

## 📖 Runbook

See [`docs/runbook.md`](docs/runbook.md) for the incident response guide covering:
- Performance alerts (CPU, disk, RAM)
- Network alerts (HTTP endpoints, VPN)
- Security alerts (SSL expiry, unknown processes)
- Hardware alerts
- SLA escalation matrix
- Ticket closure procedure

---

## 💡 Why This Project?

This toolkit replicates patterns used in enterprise support environments (ServiceNow, Jira Service Management, PagerDuty) but built from scratch to demonstrate:

- **Database design** — normalized schema with lookup tables and foreign key constraints
- **Automation thinking** — detecting problems before users report them
- **API design** — clean REST conventions, proper status codes, input validation
- **SLA awareness** — a core concept in any support role
- **Observability** — Prometheus metrics and Grafana dashboards like production environments use
- **Docker fluency** — full stack runs with a single `docker compose up`

I wrote this project to deepen my knowledge of Docker, Python, and infrastructure observability as part of my journey toward a remote Technical Support Engineer role.

---

## 📄 License

MIT — use freely, attribution appreciated.
