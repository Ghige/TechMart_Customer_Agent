"""
pytest test suite for TechMart AI Support Agent.

Run:  pytest tests/ -v
"""

import os
import sys
import pytest

# ── Allow running from project root ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use an in-memory/temp DB so tests never touch production data
os.environ.setdefault("TECHMART_DB", ":memory:")

from backend.policies.refund_policy import evaluate, RETURN_WINDOWS
from backend.database.crm import init_db, get_customer_by_email, get_customer_by_id, get_all_customers
from backend.tools.refund_tools import tool_lookup_customer, tool_evaluate_refund, dispatch


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Give every test its own temp SQLite file."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("TECHMART_DB", db_file)
    # Patch the module-level DB_PATH used by crm.py
    import backend.database.crm as crm_mod
    from pathlib import Path
    monkeypatch.setattr(crm_mod, "DB_PATH", Path(db_file))
    init_db()
    yield


# ─────────────────────────────────────────────────────────────────────────────
# 1. Policy engine unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReturnWindows:
    def test_standard_window(self):
        assert RETURN_WINDOWS["Standard"] == 30

    def test_premium_window(self):
        assert RETURN_WINDOWS["Premium"] == 45

    def test_vip_window(self):
        assert RETURN_WINDOWS["VIP"] == 60


class TestPolicyEvaluate:

    def _customer(self, tier="Standard"):
        return {"id": "C999", "name": "Test User", "tier": tier}

    def _order(self, **kwargs):
        base = {
            "id": "ORD-TEST", "item": "Widget", "amount": 999,
            "days_since_delivery": 10, "open_box": False, "prev_refund_denied": False,
        }
        base.update(kwargs)
        return base

    # Happy path
    def test_valid_defect_approved(self):
        result = evaluate(self._customer(), self._order(), "headphones stopped working")
        assert result["decision"] == "APPROVED"
        assert result["refund_amount"] == 999

    def test_doa_approved(self):
        result = evaluate(self._customer(), self._order(), "dead on arrival")
        assert result["decision"] == "APPROVED"

    def test_wrong_item_approved(self):
        result = evaluate(self._customer(), self._order(), "wrong item shipped")
        assert result["decision"] == "APPROVED"

    # Denial scenarios
    def test_changed_mind_denied(self):
        result = evaluate(self._customer(), self._order(), "I changed my mind")
        assert result["decision"] == "DENIED"

    def test_found_cheaper_denied(self):
        result = evaluate(self._customer(), self._order(), "found cheaper elsewhere")
        assert result["decision"] == "DENIED"

    def test_gifted_denied(self):
        result = evaluate(self._customer(), self._order(), "I gifted it to someone")
        assert result["decision"] == "DENIED"

    # Return window
    def test_standard_expired_denied(self):
        result = evaluate(self._customer("Standard"), self._order(days_since_delivery=31), "not working")
        assert result["decision"] == "DENIED"
        assert "30" in result["reason"]

    def test_premium_within_window(self):
        result = evaluate(self._customer("Premium"), self._order(days_since_delivery=40), "item broken")
        assert result["decision"] == "APPROVED"

    def test_premium_expired_denied(self):
        result = evaluate(self._customer("Premium"), self._order(days_since_delivery=46), "broken")
        assert result["decision"] == "DENIED"

    def test_vip_within_window(self):
        result = evaluate(self._customer("VIP"), self._order(days_since_delivery=59), "defect")
        assert result["decision"] == "APPROVED"

    def test_vip_expired_denied(self):
        result = evaluate(self._customer("VIP"), self._order(days_since_delivery=61), "broken")
        assert result["decision"] == "DENIED"

    # Open-box
    def test_open_box_denied(self):
        result = evaluate(self._customer(), self._order(open_box=True), "changed my mind")
        assert result["decision"] == "DENIED"

    # High-value
    def test_high_value_defect_conditions(self):
        result = evaluate(self._customer(), self._order(amount=60_000), "dead on arrival")
        assert result["decision"] == "APPROVED_WITH_CONDITIONS"

    def test_high_value_no_defect_keyword_falls_through(self):
        """Changed mind on high-value should still be DENIED (rule 3 triggers first)."""
        result = evaluate(self._customer(), self._order(amount=60_000), "changed my mind")
        assert result["decision"] == "DENIED"

    # VIP goodwill
    def test_vip_goodwill_keep_item(self):
        result = evaluate(self._customer("VIP"), self._order(amount=10_000), "device is faulty")
        assert result["decision"] == "APPROVED"
        assert result.get("keep_item") is True

    def test_standard_no_keep_item(self):
        result = evaluate(self._customer("Standard"), self._order(amount=10_000), "device is faulty")
        assert result["decision"] == "APPROVED"
        assert not result.get("keep_item")

    # Ambiguous
    def test_ambiguous_needs_info(self):
        result = evaluate(self._customer(), self._order(), "issue")
        assert result["decision"] == "NEEDS_INFO"

    # Policy logs always present
    def test_policy_logs_always_returned(self):
        for reason in ["broken", "changed my mind", "found cheaper"]:
            result = evaluate(self._customer(), self._order(), reason)
            assert "policy_logs" in result
            assert isinstance(result["policy_logs"], list)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CRM database tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCRM:

    def test_all_15_customers_seeded(self):
        customers = get_all_customers()
        assert len(customers) == 15

    def test_lookup_by_email_found(self):
        c = get_customer_by_email("priya.sharma@gmail.com")
        assert c is not None
        assert c["name"] == "Priya Sharma"
        assert c["tier"] == "Premium"

    def test_lookup_case_insensitive(self):
        c = get_customer_by_email("PRIYA.SHARMA@GMAIL.COM")
        assert c is not None

    def test_lookup_unknown_email_returns_none(self):
        c = get_customer_by_email("nobody@nowhere.com")
        assert c is None

    def test_lookup_by_id(self):
        c = get_customer_by_id("C001")
        assert c["email"] == "priya.sharma@gmail.com"

    def test_lookup_unknown_id_returns_none(self):
        assert get_customer_by_id("C999") is None

    def test_customer_has_orders(self):
        c = get_customer_by_email("vikram.singh@gmail.com")
        assert len(c["orders"]) == 2

    def test_open_box_flag(self):
        c = get_customer_by_email("aditya.verma@gmail.com")
        order = c["orders"][0]
        assert order["open_box"] is True

    def test_prev_refund_denied_flag(self):
        c = get_customer_by_email("vikram.singh@gmail.com")
        denied_order = next(o for o in c["orders"] if o["id"] == "ORD-2209")
        assert denied_order["prev_refund_denied"] is True

    def test_vip_customers_count(self):
        customers = get_all_customers()
        vips = [c for c in customers if c["tier"] == "VIP"]
        assert len(vips) == 4  # Sneha, Ananya, Aditya, Lakshmi

    def test_standard_customers_count(self):
        customers = get_all_customers()
        standard = [c for c in customers if c["tier"] == "Standard"]
        assert len(standard) == 6


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tool dispatcher tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTools:

    def test_lookup_customer_found(self):
        result = tool_lookup_customer("priya.sharma@gmail.com")
        assert "error" not in result
        assert result["name"] == "Priya Sharma"

    def test_lookup_customer_not_found(self):
        result = tool_lookup_customer("ghost@test.com")
        assert "error" in result

    def test_evaluate_refund_approved(self):
        result = tool_evaluate_refund("C001", "ORD-7821", "headphones stopped working")
        assert result["decision"] == "APPROVED"

    def test_evaluate_refund_denied_changed_mind(self):
        result = tool_evaluate_refund("C013", "ORD-0432", "changed my mind")
        assert result["decision"] == "DENIED"

    def test_evaluate_refund_denied_window_expired(self):
        result = tool_evaluate_refund("C010", "ORD-0765", "not working")
        assert result["decision"] == "DENIED"

    def test_evaluate_refund_high_value_conditions(self):
        result = tool_evaluate_refund("C009", "ORD-0876", "dead on arrival")
        assert result["decision"] == "APPROVED_WITH_CONDITIONS"

    def test_evaluate_refund_open_box_denied(self):
        result = tool_evaluate_refund("C012", "ORD-0543", "changed my mind")
        assert result["decision"] == "DENIED"

    def test_evaluate_refund_unknown_customer(self):
        result = tool_evaluate_refund("C999", "ORD-9999", "broken")
        assert result["decision"] == "DENIED"

    def test_evaluate_refund_unknown_order(self):
        result = tool_evaluate_refund("C001", "ORD-9999", "broken")
        assert result["decision"] == "DENIED"

    def test_vip_doa_approved_keep_item(self):
        # Sneha Iyer: VIP, iPad Pro, ₹79,900 — goodwill applies
        result = tool_evaluate_refund("C005", "ORD-3301", "not turning on dead on arrival")
        assert result["decision"] == "APPROVED_WITH_CONDITIONS"  # >50k requires photo

    def test_dispatch_unknown_tool(self):
        result = dispatch("nonexistent_tool", {})
        assert "error" in result

    def test_dispatch_lookup(self):
        result = dispatch("lookup_customer", {"email": "priya.sharma@gmail.com"})
        assert result["name"] == "Priya Sharma"

    def test_dispatch_evaluate(self):
        result = dispatch("evaluate_refund", {
            "customer_id": "C001", "order_id": "ORD-7821", "reason": "broken"
        })
        assert result["decision"] == "APPROVED"


# ─────────────────────────────────────────────────────────────────────────────
# 4. FastAPI route tests (no real Claude calls)
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIRoutes:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_customers_endpoint(self, client):
        r = client.get("/customers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 15

    def test_policy_endpoint(self, client):
        r = client.get("/policy")
        assert r.status_code == 200
        assert "REFUND POLICY" in r.json()["policy"]

    def test_chat_empty_message(self, client):
        r = client.post("/chat", json={"message": "", "history": []})
        assert r.status_code == 422

    def test_chat_whitespace_message(self, client):
        r = client.post("/chat", json={"message": "   ", "history": []})
        assert r.status_code == 422
