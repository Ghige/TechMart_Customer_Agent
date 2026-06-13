# TechMart AI Customer Support Agent

A production-grade AI Customer Support Agent that processes or denies e-commerce refunds,  
built with **FastAPI + LangGraph + OpenAI GPT-4o + SQLite**.


## Project Structure

```
techmart_agent/
├── main.py                        ← Thin FastAPI entry point
├── requirements.txt
├── Dockerfile                     ← Multi-stage Docker build
├── docker-compose.yml             ← Local Docker Compose setup
├── render.yaml                    ← One-click Render deploy config
├── .dockerignore
├── README.md
│
├── backend/
│   ├── agents/
│   │   └── support_agent.py       ← LangGraph graph (call_model → run_tools loop)
│   ├── tools/
│   │   └── refund_tools.py        ← Tool schemas + execution logic
│   ├── database/
│   │   └── crm.py                 ← SQLite CRM — schema, seed, query helpers
│   ├── policies/
│   │   └── refund_policy.py       ← Pure-function policy engine (fully testable)
│   └── api/
│       └── routes.py              ← FastAPI route handlers
│
├── frontend/
│   └── index.html                 ← Single-file UI (chat + admin dashboard)
│
└── tests/
    └── test_refund_engine.py      ← pytest suite (50+ assertions)
```

---

## Setup & Run

### Option A — Docker Compose (recommended)

```bash
# 1. Clone / unzip the project
cd techmart_agent

# 2. Set your OpenAI key
export OPENAI_API_KEY=sk-...

# 3. Build and start
docker compose up --build

# 4. Open in browser
open http://localhost:8000
```

The SQLite database is persisted in a named Docker volume (`techmart_data`) and survives restarts.

---

### Option B — Local Python

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your OpenAI key
export OPENAI_API_KEY=sk-...      # macOS / Linux
# set OPENAI_API_KEY=sk-...       # Windows CMD
# $env:OPENAI_API_KEY="sk-..."    # Windows PowerShell

# 3. Start the server
python main.py

# 4. Open in browser
open http://localhost:8000

# 5. Run tests
pytest tests/ -v
```

---

## Deploy to Render

The repo ships a `render.yaml` for zero-config deployment.

1. Push this folder to a GitHub repository.
2. Go to [render.com](https://render.com) → **New → Blueprint** → connect your repo.
3. In the Render dashboard, set the `OPENAI_API_KEY` environment variable (never commit it).
4. Click **Deploy**. Render builds the Docker image and serves it at  
   `https://<your-service-name>.onrender.com`.

---

## Architecture

```
User Message
     │
     ▼
FastAPI POST /chat  (backend/api/routes.py)
     │
     ▼
LangGraph Agent Loop  (backend/agents/support_agent.py)
  ┌──────────────────────────────────────────────┐
  │  Node: call_model                            │
  │    → OpenAI GPT-4o (function calling)        │
  │           │                                  │
  │           ▼ (if tools requested)             │
  │  Node: run_tools                             │
  │    → backend/tools/refund_tools.py           │
  │        → lookup_customer()                   │
  │            └─ backend/database/crm.py        │
  │        → evaluate_refund()                   │
  │            └─ backend/policies/refund_policy │
  │           │                                  │
  │           └──────────► call_model (loop)     │
  │  (exits when finish_reason = stop)           │
  └──────────────────────────────────────────────┘
     │
     ▼
Return: reply + reasoning_logs + tool_calls
     │
     ▼
frontend/index.html renders chat + reasoning trace panel
```

---

## Agent Tools

| Tool | Module | Description |
|------|--------|-------------|
| `lookup_customer(email)` | `backend/tools/refund_tools.py` | Fetches customer profile + order history from SQLite CRM |
| `evaluate_refund(customer_id, order_id, reason)` | `backend/tools/refund_tools.py` | Runs policy engine, returns APPROVED / DENIED / APPROVED_WITH_CONDITIONS / NEEDS_INFO |

---

## Refund Policy Engine

`backend/policies/refund_policy.py` — a pure function `evaluate(customer, order, reason) → dict`.  
Checks in order:

| # | Rule | Result |
|---|------|--------|
| 1 | Return window by tier (Standard 30d, Premium 45d, VIP 60d) | DENIED if exceeded |
| 2 | Open-box / demo units | DENIED (non-returnable) |
| 3 | Invalid reasons — "changed mind", "found cheaper", "gifted" | DENIED |
| 4 | Previous denied refund on account | Flagged for supervisor escalation |
| 5 | High-value orders > ₹50,000 | APPROVED_WITH_CONDITIONS (photo evidence required) |
| 6 | Valid defect keyword or sufficiently descriptive reason | APPROVED |
| 7 | Ambiguous / unclear | NEEDS_INFO |

VIP goodwill: when APPROVED and order > ₹5,000, customer keeps the item.

---

## Database

Customer data is stored in a **SQLite database** (`techmart.db`), automatically seeded with 15 profiles on first run. No manual setup needed.

```python
from backend.database import get_customer_by_email, get_all_customers
```

To inspect or reset:
```bash
python -m backend.database.crm
```

---

## Demo Scenarios

| Scenario | Email | Order | Reason | Expected |
|----------|-------|-------|--------|----------|
| Valid defect | priya.sharma@gmail.com | ORD-7821 | headphones stopped working | ✅ APPROVED |
| Changed mind | pooja.gupta@gmail.com | ORD-0432 | changed my mind | ❌ DENIED |
| Expired window | rohan.desai@gmail.com | ORD-0765 | not working | ❌ DENIED (81d > 30d) |
| Open-box | aditya.verma@gmail.com | ORD-0543 | changed my mind | ❌ DENIED (open-box) |
| High-value defect | divya.pillai@gmail.com | ORD-0876 | dead on arrival | ⚠️ APPROVED WITH CONDITIONS |
| VIP DOA | sneha.iyer@gmail.com | ORD-3301 | not turning on | ✅ APPROVED (photo req'd) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the frontend UI |
| `POST` | `/chat` | Main agent endpoint |
| `GET` | `/customers` | Returns all 15 CRM profiles |
| `GET` | `/policy` | Returns the refund policy text |
| `GET` | `/health` | Liveness probe |

---

## Testing

```bash
pytest tests/ -v
```

The test suite covers:

- **Policy engine** — all 7 rules, all 3 tiers, edge cases (VIP goodwill, high-value, open-box, ambiguous)
- **CRM database** — seeding, lookup by email + ID, flag fields, tier counts
- **Tool dispatcher** — all 6 demo scenarios, unknown tool/customer/order error handling  
- **API routes** — health, customers, policy, empty-message validation

Tests use a **temporary SQLite file** per test — never touching the production DB.

---

## Error Handling

| Failure mode | Response |
|---|---|
| OPENAI_API_KEY missing | Clear startup error with instructions |
| OpenAI API connection error | HTTP 503 with user-friendly message |
| Rate limit hit | HTTP 503, retryable message |
| Unknown customer email | Tool returns `{"error": "..."}` → GPT-4o asks for correct email |
| Unknown order ID | Tool returns `{"error": "..."}` → GPT-4o asks for correct order |
| Tool crash | Caught, logged, returns NEEDS_INFO with human escalation note |

---

## CRM — 15 Customer Profiles

| Tier | Customers | Return Window |
|------|-----------|---------------|
| Standard (6) | Rahul, Kavya, Kiran, Vikram, Pooja, Siddharth | 30 days |
| Premium (4)  | Priya, Arjun, Meera, Divya | 45 days |
| VIP (4)      | Sneha, Ananya, Aditya, Lakshmi | 60 days |

Special flags: Vikram has a previous denied refund; Aditya has an open-box laptop.

---

## Design Decisions

**Why OpenAI GPT-4o?**  
GPT-4o has best-in-class function calling reliability and low latency. The tool schema conversion from Anthropic format to OpenAI format is handled once in `support_agent.py`; swapping models requires changing only the `model=` string.

**Why LangGraph over CrewAI?**  
Single-agent loop with deterministic routing (`should_continue`) is all this problem needs. LangGraph's explicit state machine is easier to test and reason about than CrewAI's crew abstraction.

**Why SQLite over hardcoded Python dict?**  
SQLite demonstrates proper data-layer separation. The CRM module is swappable to PostgreSQL by changing one import.

**Why Docker multi-stage build?**  
Builder stage installs deps; runtime stage copies only the venv — resulting image is ~200 MB instead of ~600 MB.

**Scalability path:**  
- Replace SQLite with PostgreSQL + SQLAlchemy  
- Add Redis caching on `lookup_customer`  
- Rate-limit `/chat` per IP with `slowapi`  
- Auth middleware to protect `/customers` (exposes all PII — admin only)

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ Yes | Your OpenAI API key (`sk-...`) |
| `TECHMART_DB_PATH` | No | Path to SQLite file (default: `techmart.db`) |
