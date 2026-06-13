"""
FastAPI route definitions.
Imported by main.py — keeps the app entry-point thin.
"""

from __future__ import annotations
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr

from backend.agents import agent, AgentState
from backend.database import get_all_customers
from backend.policies import POLICY_TEXT

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    reply: str
    reasoning_logs: list[dict]
    tool_calls: list[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_reply(messages: list) -> str:
    """Walk messages in reverse to find the last assistant text."""
    for m in reversed(messages):
        content = m["content"] if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
            if texts:
                return " ".join(texts)
    return "I'm sorry, I couldn't generate a response. Please try again."


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Main agent endpoint — runs the LangGraph loop and returns structured output."""
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    messages = list(req.history) + [{"role": "user", "content": req.message}]
    initial_state: AgentState = {
        "messages": messages,
        "reasoning_logs": [],
        "tool_calls_log": [],
    }

    try:
        result = await asyncio.to_thread(agent.invoke, initial_state)
    except RuntimeError as exc:
        # Surface clean API/auth errors to the frontend
        logger.error("Agent invoke failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected agent error")
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")

    return ChatResponse(
        reply=_extract_reply(result["messages"]),
        reasoning_logs=result.get("reasoning_logs", []),
        tool_calls=result.get("tool_calls_log", []),
    )


@router.get("/customers")
def get_customers():
    """Return all CRM profiles (admin use)."""
    try:
        return get_all_customers()
    except Exception as exc:
        logger.exception("Failed to load CRM customers")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@router.get("/policy")
def get_policy():
    """Return the plain-text refund policy."""
    return {"policy": POLICY_TEXT}


@router.get("/health")
def health():
    """Lightweight liveness probe."""
    return {"status": "ok"}
