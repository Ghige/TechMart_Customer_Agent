# TechMart AI Customer Support Agent

A production-style AI Customer Support Agent that automates e-commerce refund decisions using **OpenAI GPT-4o, LangGraph, FastAPI, and SQLite**.

The system retrieves customer information from a CRM database, evaluates refund eligibility through a deterministic policy engine, and returns transparent decisions with real-time reasoning traces.

---

## Demo Video

Loom Walkthrough:

https://www.loom.com/share/c9cd5abdb4f141fda46024aec820383a
---

## Features

* AI-powered refund processing
* OpenAI GPT-4o Function Calling
* LangGraph Agent Workflow
* Deterministic Refund Policy Engine
* SQLite CRM Database
* Customer Support Chat Interface
* Admin Dashboard with Reasoning Logs
* Real-Time Tool Execution Trace
* Dockerized Deployment
* Automated Test Suite
* Production-Ready Project Structure

---

## Tech Stack

### Backend

* Python
* FastAPI
* LangGraph
* OpenAI GPT-4o

### Database

* SQLite

### Frontend

* HTML
* CSS
* JavaScript

### DevOps

* Docker
* Docker Compose
* Render
* GitHub

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/Ghige/TechMart_Customer_Agent.git
cd TechMart_Customer_Agent
```

### 2. Create Environment File

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Example:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx
```

Never commit your real API key to GitHub.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Application

```bash
python main.py
```

### 5. Open Browser

```text
http://localhost:8000
```

---

## Project Overview

TechMart AI Customer Support Agent simulates a real-world customer support workflow.

The system:

1. Receives a customer refund request.
2. Retrieves customer and order details from the CRM database.
3. Evaluates refund eligibility using a rule-based policy engine.
4. Uses GPT-4o function calling to orchestrate tool usage.
5. Returns a final customer-facing response.
6. Displays reasoning traces and tool execution logs for transparency.

The language model never directly decides refund outcomes.

All approval and denial decisions are enforced by the policy engine, ensuring deterministic and auditable business behavior.

---

## Architecture

```text
User Message
      │
      ▼
FastAPI API Layer
      │
      ▼
LangGraph Agent
      │
      ├── lookup_customer()
      │       │
      │       ▼
      │   SQLite CRM
      │
      └── evaluate_refund()
              │
              ▼
      Refund Policy Engine
              │
              ▼
      Final Response
              │
              ▼
Frontend + Reasoning Dashboard
```
