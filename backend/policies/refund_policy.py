"""
TechMart Refund Policy Engine.
All business logic lives here — isolated, testable, import-friendly.
"""

RETURN_WINDOWS = {"VIP": 60, "Premium": 45, "Standard": 30}

POLICY_TEXT = """
REFUND POLICY — TechMart India

1. RETURN WINDOW (from delivery date):
   - Standard: 30 days  
   - Premium:  45 days
   - VIP:      60 days

2. VALID REASONS: defective/DOA, wrong item shipped, item not as described, shipping damage.

3. INVALID REASONS (hold the line): changed mind, found cheaper elsewhere, gifted to someone,
   opened and used (unless defective).

4. SPECIAL RULES:
   - Open-box / demo units: non-returnable unless defective.
   - Orders > ₹50,000: require photographic proof of defect before approval.
   - Account with previous denied refund: escalate to supervisor.
   - VIP refunds > ₹5,000: customer keeps the item (goodwill policy).

5. PROCESSING: 5–7 business days back to original payment method.
"""

INVALID_KEYWORDS = [
    "changed my mind", "changed mind", "change of mind",
    "no longer need", "found cheaper", "found it cheaper",
    "don't want", "dont want", "do not want",
    "gifted", "doesn't like", "doesnt like", "don't like", "dont like",
]

VALID_KEYWORDS = [
    "defect", "broken", "not as described", "wrong item", "damaged",
    "doa", "dead on arrival", "not working", "stopped working",
    "never worked", "faulty","not turning on","won't turn on","does not turn on"
]


def evaluate(customer: dict, order: dict, reason: str) -> dict:
    """
    Pure-function policy engine.

    Args:
        customer: dict with keys id, name, tier
        order:    dict with keys id, amount, days_since_delivery, open_box, prev_refund_denied
        reason:   free-text reason from customer

    Returns:
        dict with decision, reason, policy_logs, and optional refund_amount / keep_item
    """
    logs: list[str] = []
    tier = customer.get("tier", "Standard")
    window = RETURN_WINDOWS.get(tier, 30)
    days = order.get("days_since_delivery", 0)
    amount = order.get("amount", 0)
    r = reason.lower()

    logs.append(f"Tier={tier} → window={window}d | delivered {days}d ago")

    # ── Rule 1: return window ──────────────────────────────────────────────────
    if days > window:
        logs.append(f"FAIL: {days}d > {window}d window")
        return {
            "decision": "DENIED",
            "reason": (
                f"Return window expired. {tier} customers have {window} days; "
                f"this order was delivered {days} days ago."
            ),
            "policy_logs": logs,
        }
    logs.append(f"PASS: within {window}d window")

    # ── Rule 2: open-box ───────────────────────────────────────────────────────
    if order.get("open_box"):
        logs.append("FAIL: open-box item — non-returnable")
        return {
            "decision": "DENIED",
            "reason": "Open-box and demo units cannot be returned unless defective.",
            "policy_logs": logs,
        }

    # ── Rule 3: invalid reason ─────────────────────────────────────────────────
    if any(k in r for k in INVALID_KEYWORDS):
        logs.append(f"FAIL: reason '{reason}' is policy-excluded")
        return {
            "decision": "DENIED",
            "reason": (
                "This reason doesn't qualify under our policy. "
                "We process refunds for defects, wrong items, or items not as described."
            ),
            "policy_logs": logs,
        }

    # ── Rule 4: previous denied refund ────────────────────────────────────────
    if order.get("prev_refund_denied"):
        logs.append("FLAG: previous denied refund on account → supervisor escalation")

    # ── Rule 5: high-value order ───────────────────────────────────────────────
    if amount > 50_000 and any(k in r for k in VALID_KEYWORDS):
        logs.append(f"NOTE: high-value order ₹{amount:,} → photo evidence required")
        return {
            "decision": "APPROVED_WITH_CONDITIONS",
            "reason": (
                "Refund approved, but photographic evidence of the defect is required "
                "before processing (orders above ₹50,000)."
            ),
            "refund_amount": amount,
            "policy_logs": logs,
        }

    # ── Rule 6: valid defect or sufficiently detailed reason ──────────────────
    has_valid_keyword = any(k in r for k in VALID_KEYWORDS)
    if has_valid_keyword or (not any(k in r for k in INVALID_KEYWORDS) and len(reason) > 10):
        logs.append("PASS: valid refund reason")
        keep_item = amount > 5_000 and tier == "VIP"
        return {
            "decision": "APPROVED",
            "reason": "Refund approved. Meets all policy criteria.",
            "refund_amount": amount,
            "keep_item": keep_item,
            "processing_days": "5–7 business days",
            "policy_logs": logs,
        }

    # ── Fallback: ambiguous ────────────────────────────────────────────────────
    logs.append("UNCLEAR: ambiguous reason — need more details")
    return {
        "decision": "NEEDS_INFO",
        "reason": "Could you provide more details about the issue with your order?",
        "policy_logs": logs,
    }
