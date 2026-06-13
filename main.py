"""
TechMart AI Customer Support Agent
Entry point — kept deliberately thin.

Start with:
    python main.py
or:
    uvicorn main:app --reload
"""

import logging
from pathlib import Path

# ── Load .env FIRST, before any other imports that might read env vars ────────
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.database import init_db
from backend.api import router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("techmart")

# ── DB init (idempotent) ──────────────────────────────────────────────────────
init_db()
logger.info("SQLite CRM initialised ✓")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="TechMart AI Support Agent",
    description="LangGraph + GPT-4o agent for e-commerce refund processing.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

FRONTEND = Path("frontend/index.html")


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if not FRONTEND.exists():
        return HTMLResponse("<h1>frontend/index.html not found</h1>", status_code=404)
    return HTMLResponse(FRONTEND.read_text(encoding="utf-8"))

# ── Dev server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
