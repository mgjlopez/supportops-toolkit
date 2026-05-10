# 🛠️ SupportOps Toolkit

![CI](https://github.com/YOUR_USERNAME/supportops-toolkit/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python)
![SQL Server](https://img.shields.io/badge/SQL_Server-2022-red?logo=microsoftsqlserver)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/license-MIT-green)

> A production-style IT support automation system built with Python, FastAPI, SQL Server, and Docker.  
> Simulates real-world workflows: auto-ticketing, SLA escalation, health monitoring, and reporting.

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

Everything runs locally via **Docker Compose** — no paid cloud services needed.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                  Docker Network                  │
│                                                 │
│  ┌─────────────┐      ┌──────────────────────┐  │
│  │  SQL Server │◄─────│   FastAPI (port 8000)│  │
│  │  Developer  │      │   REST API + Logic   │  │
│  │  port 1433  │      └──────────┬───────────┘  │
│  └─────────────┘                 │               │
│                         ┌────────▼────────┐      │
│                         │  Python Scripts │      │
│                         │  (schedulers)   │      │
│                         └─────────────────┘      │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.10+ (for running scripts outside Docker)

### 1. Clone and start

```bash
git clone https://github.com/YOUR_USERNAME/supportops-toolkit.git
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

### 4. Access the API

- **Swagger UI:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

---

## 📁 Project Structure

```
supportops-toolkit/
├── api/                    # FastAPI application
│   ├── main.py             # App entrypoint + routes
│   ├── models.py           # Pydantic models
│   ├── database.py         # SQLAlchemy + SQL Server connection
│   └── routers/
│       ├── tickets.py      # Ticket CRUD endpoints
│       └── reports.py      # Reporting endpoints
├── automation/             # Core automation scripts
│   ├── health_monitor.py   # System health checks → auto-tickets
│   ├── escalation_engine.py# SLA breach detection + escalation
│   └── report_generator.py # Generate CSV/console reports
├── db/
│   ├── migrate.py          # Schema creation
│   ├── seed.py             # Sample data loader
│   └── schema.sql          # Raw SQL schema (reference)
├── tests/
│   ├── test_tickets.py     # API endpoint tests
│   └── test_escalation.py  # Escalation logic tests
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
GET    /tickets              List all tickets (filterable)
POST   /tickets              Create a ticket manually
GET    /tickets/{id}         Get ticket detail
PATCH  /tickets/{id}         Update status/assignee
DELETE /tickets/{id}         Close/delete ticket

GET    /reports/summary      Ticket volume by category
GET    /reports/sla          SLA compliance rate
GET    /reports/resolution   Average resolution time
GET    /health               Service health check
```

---

## 🧪 Running Tests

```bash
docker compose exec api pytest tests/ -v
```

---

## 💡 Why This Project?

This toolkit replicates patterns used in enterprise support environments (ServiceNow, Jira Service Management, PagerDuty) but built from scratch to demonstrate:

- **Database design** for operational data (tickets, events, assets)
- **Automation thinking** — detecting problems before users report them
- **API design** — clean REST conventions, proper status codes, validation
- **SLA awareness** — a core concept in any support role
- **Docker fluency** — run anywhere, no environment excuses

I wrote this project to learn the usage of Docker and improve my knowledge of Python

---

## 📄 License

MIT — use freely, attribution appreciated.
