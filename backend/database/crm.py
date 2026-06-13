"""
CRM Database layer backed by SQLite.
Run `python -m backend.database.crm` to initialise / inspect the DB.
"""

import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("TECHMART_DB_PATH", "techmart.db"))

# ── Seed data (15 profiles) ───────────────────────────────────────────────────
SEED_CUSTOMERS = [
    {
        "id": "C001", "name": "Priya Sharma",    "email": "priya.sharma@gmail.com",    "tier": "Premium",
        "orders": [{"id": "ORD-7821", "item": "Sony WH-1000XM5 Headphones",  "amount": 3499,   "days_since_delivery": 22, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C002", "name": "Rahul Mehta",     "email": "rahul.mehta@gmail.com",     "tier": "Standard",
        "orders": [{"id": "ORD-6654", "item": "OnePlus Watch 2",              "amount": 1499,   "days_since_delivery": 7,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C003", "name": "Kavya Nair",      "email": "kavya.nair@gmail.com",      "tier": "Standard",
        "orders": [{"id": "ORD-5523", "item": "Boat Airdopes 141",            "amount": 799,    "days_since_delivery": 11, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C004", "name": "Arjun Patel",     "email": "arjun.patel@gmail.com",     "tier": "Premium",
        "orders": [{"id": "ORD-4411", "item": "Logitech MX Master 3",         "amount": 5999,   "days_since_delivery": 69, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C005", "name": "Sneha Iyer",      "email": "sneha.iyer@gmail.com",      "tier": "VIP",
        "orders": [{"id": "ORD-3301", "item": "iPad Pro 11-inch",             "amount": 79900,  "days_since_delivery": 2,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C006", "name": "Vikram Singh",    "email": "vikram.singh@gmail.com",    "tier": "Standard",
        "orders": [
            {"id": "ORD-2210", "item": "Boat Rockerz 450",  "amount": 999,  "days_since_delivery": 8,  "open_box": False, "prev_refund_denied": False},
            {"id": "ORD-2209", "item": "USB-C Hub 7-in-1",  "amount": 1299, "days_since_delivery": 25, "open_box": False, "prev_refund_denied": True},
        ],
    },
    {
        "id": "C007", "name": "Ananya Roy",      "email": "ananya.roy@gmail.com",      "tier": "VIP",
        "orders": [{"id": "ORD-1122", "item": "Bose QuietComfort 45",         "amount": 24999,  "days_since_delivery": 4,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C008", "name": "Kiran Kumar",     "email": "kiran.kumar@gmail.com",     "tier": "Standard",
        "orders": [{"id": "ORD-0981", "item": "Realme Buds Air 3",            "amount": 599,    "days_since_delivery": 30, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C009", "name": "Divya Pillai",    "email": "divya.pillai@gmail.com",    "tier": "Premium",
        "orders": [{"id": "ORD-0876", "item": "Samsung Galaxy Tab S9",        "amount": 54999,  "days_since_delivery": 1,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C010", "name": "Rohan Desai",     "email": "rohan.desai@gmail.com",     "tier": "Standard",
        "orders": [{"id": "ORD-0765", "item": "Mi Robot Vacuum",              "amount": 12999,  "days_since_delivery": 81, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C011", "name": "Meera Krishnan",  "email": "meera.krishnan@gmail.com",  "tier": "Premium",
        "orders": [{"id": "ORD-0654", "item": "Apple AirPods Pro 2",          "amount": 19900,  "days_since_delivery": 9,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C012", "name": "Aditya Verma",    "email": "aditya.verma@gmail.com",    "tier": "VIP",
        "orders": [{"id": "ORD-0543", "item": "Dell XPS 15 Laptop",           "amount": 129000, "days_since_delivery": 20, "open_box": True,  "prev_refund_denied": False}],
    },
    {
        "id": "C013", "name": "Pooja Gupta",     "email": "pooja.gupta@gmail.com",     "tier": "Standard",
        "orders": [{"id": "ORD-0432", "item": "Xiaomi Smart Band 8",          "amount": 2499,   "days_since_delivery": 6,  "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C014", "name": "Siddharth Joshi", "email": "siddharth.joshi@gmail.com", "tier": "Standard",
        "orders": [{"id": "ORD-0321", "item": "Noise ColorFit Pro 4",         "amount": 1799,   "days_since_delivery": 55, "open_box": False, "prev_refund_denied": False}],
    },
    {
        "id": "C015", "name": "Lakshmi Menon",   "email": "lakshmi.menon@gmail.com",   "tier": "VIP",
        "orders": [{"id": "ORD-0210", "item": "Sony PlayStation 5",           "amount": 49990,  "days_since_delivery": 3,  "open_box": False, "prev_refund_denied": False}],
    },
]


# ── Schema & seed ─────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False) -> None:
    """Create tables and seed data. Safe to call multiple times."""
    conn = _get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id    TEXT PRIMARY KEY,
            name  TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            tier  TEXT NOT NULL CHECK(tier IN ('Standard','Premium','VIP'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id                  TEXT PRIMARY KEY,
            customer_id         TEXT NOT NULL REFERENCES customers(id),
            item                TEXT NOT NULL,
            amount              INTEGER NOT NULL,
            days_since_delivery INTEGER NOT NULL,
            open_box            INTEGER NOT NULL DEFAULT 0,
            prev_refund_denied  INTEGER NOT NULL DEFAULT 0
        );
    """)

    if force:
        cur.execute("DELETE FROM orders")
        cur.execute("DELETE FROM customers")

    for c in SEED_CUSTOMERS:
        cur.execute(
            "INSERT OR IGNORE INTO customers(id,name,email,tier) VALUES(?,?,?,?)",
            (c["id"], c["name"], c["email"], c["tier"]),
        )
        for o in c["orders"]:
            cur.execute(
                """INSERT OR IGNORE INTO orders
                   (id,customer_id,item,amount,days_since_delivery,open_box,prev_refund_denied)
                   VALUES(?,?,?,?,?,?,?)""",
                (o["id"], c["id"], o["item"], o["amount"],
                 o["days_since_delivery"], int(o["open_box"]), int(o["prev_refund_denied"])),
            )

    conn.commit()
    conn.close()


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_customer_by_email(email: str) -> dict | None:
    """Return full customer profile + orders, or None if not found."""
    conn = _get_conn()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT id, name, email, tier FROM customers WHERE lower(email)=lower(?)",
        (email.strip(),),
    ).fetchone()

    if not row:
        conn.close()
        return None

    orders = cur.execute(
        """SELECT id, item, amount, days_since_delivery, open_box, prev_refund_denied
           FROM orders WHERE customer_id=?""",
        (row["id"],),
    ).fetchall()

    conn.close()

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "tier": row["tier"],
        "orders": [
            {
                "id": o["id"],
                "item": o["item"],
                "amount": o["amount"],
                "days_since_delivery": o["days_since_delivery"],
                "open_box": bool(o["open_box"]),
                "prev_refund_denied": bool(o["prev_refund_denied"]),
            }
            for o in orders
        ],
    }


def get_customer_by_id(customer_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT email FROM customers WHERE id=?", (customer_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return get_customer_by_email(row["email"])


def get_all_customers() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT id,name,email,tier FROM customers ORDER BY id").fetchall()
    conn.close()
    result = []
    for r in rows:
        c = get_customer_by_email(r["email"])
        if c:
            result.append(c)
    return result


# ── CLI helper ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    customers = get_all_customers()
    print(f"✅ DB ready at {DB_PATH} — {len(customers)} customers loaded")
    for c in customers:
        print(f"  {c['id']} {c['name']:20s} [{c['tier']:8s}] — {len(c['orders'])} order(s)")
