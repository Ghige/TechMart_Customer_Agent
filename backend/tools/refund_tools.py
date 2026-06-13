"""
Agent tool definitions (schema for Claude) + execution logic.
Each tool is a pure function that returns a serialisable dict.
"""

from __future__ import annotations
import logging
from backend.database import get_customer_by_email, get_customer_by_id
from backend.policies import evaluate

logger = logging.getLogger(__name__)

# ── Anthropic tool schemas ────────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "lookup_customer",
        "description": (
            "Look up a customer's CRM profile and full order history using their email address. "
            "Always call this first before evaluating any refund."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Customer's registered email address"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "evaluate_refund",
        "description": (
            "Evaluate whether a refund should be approved or denied based on TechMart refund policy. "
            "Returns APPROVED / DENIED / APPROVED_WITH_CONDITIONS / NEEDS_INFO."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID (e.g. C001)"},
                "order_id":    {"type": "string", "description": "Order ID (e.g. ORD-7821)"},
                "reason":      {"type": "string", "description": "Customer's stated reason for the refund"},
            },
            "required": ["customer_id", "order_id", "reason"],
        },
    },
]

# ── Tool implementations ──────────────────────────────────────────────────────

def tool_lookup_customer(email: str) -> dict:
    """Fetch customer profile from SQLite CRM."""
    try:
        customer = get_customer_by_email(email)
        if not customer:
            logger.warning("lookup_customer: no customer for email=%s", email)
            return {"error": f"No customer found with email: {email}"}
        logger.info("lookup_customer: found %s (%s)", customer["name"], customer["tier"])
        return customer
    except Exception as exc:
        logger.exception("lookup_customer failed for email=%s", email)
        return {"error": f"Database error while looking up customer: {exc}"}


def tool_evaluate_refund(customer_id: str, order_id: str, reason: str) -> dict:
    """Run the policy engine against a specific order."""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            logger.warning("evaluate_refund: customer_id=%s not found", customer_id)
            return {"decision": "DENIED", "reason": "Customer not found.", "policy_logs": []}

        order = next((o for o in customer["orders"] if o["id"] == order_id), None)
        if not order:
            logger.warning("evaluate_refund: order_id=%s not found for customer %s", order_id, customer_id)
            return {"decision": "DENIED", "reason": f"Order {order_id} not found on this account.", "policy_logs": []}

        result = evaluate(customer, order, reason)
        logger.info(
            "evaluate_refund: customer=%s order=%s → %s",
            customer_id, order_id, result.get("decision"),
        )
        return result

    except Exception as exc:
        logger.exception("evaluate_refund crashed for customer=%s order=%s", customer_id, order_id)
        return {
            "decision": "NEEDS_INFO",
            "reason": "An internal error occurred while evaluating your refund. A human agent will follow up.",
            "policy_logs": [f"ERROR: {exc}"],
        }


# ── Dispatcher ────────────────────────────────────────────────────────────────

def dispatch(name: str, inputs: dict) -> dict:
    """Route a tool call by name. Returns an error dict for unknown tools."""
    if name == "lookup_customer":
        return tool_lookup_customer(**inputs)
    if name == "evaluate_refund":
        return tool_evaluate_refund(**inputs)
    logger.error("dispatch: unknown tool '%s'", name)
    return {"error": f"Unknown tool: {name}"}
