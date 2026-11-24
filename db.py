"""Замовлення в SQLite."""
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH, STATUSES

_conn: Optional[sqlite3.Connection] = None


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT NOT NULL,
                city        TEXT NOT NULL,
                branch      TEXT NOT NULL,
                payment     TEXT NOT NULL,
                comment     TEXT,
                subtotal    INTEGER NOT NULL,
                delivery    INTEGER NOT NULL,
                total       INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'new',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_items (
                order_id    INTEGER NOT NULL REFERENCES orders(id),
                product_id  TEXT NOT NULL,
                name        TEXT NOT NULL,
                price       INTEGER NOT NULL,
                qty         INTEGER NOT NULL,
                grind       TEXT NOT NULL
            );
            """
        )
        _conn.commit()
    return _conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_order(customer: dict, items: list[dict], subtotal: int, delivery: int) -> dict:
    conn = connect()
    now = _now()
    with conn:
        cur = conn.execute(
            """INSERT INTO orders (name, phone, city, branch, payment, comment,
                                   subtotal, delivery, total, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
            (customer["name"], customer["phone"], customer["city"], customer["branch"],
             customer["payment"], customer.get("comment", ""), subtotal, delivery,
             subtotal + delivery, now, now),
        )
        order_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)",
            [(order_id, i["id"], i["name"], i["price"], i["qty"], i["grind"]) for i in items],
        )
    return get_order(order_id)


def get_order(order_id: int) -> Optional[dict]:
    conn = connect()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return None
    order = dict(row)
    order["items"] = [dict(r) for r in conn.execute(
        "SELECT product_id, name, price, qty, grind FROM order_items WHERE order_id = ?", (order_id,)
    )]
    return order


def list_orders(status: Optional[str] = None, limit: int = 200) -> list[dict]:
    conn = connect()
    if status:
        ids = conn.execute("SELECT id FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        ids = conn.execute("SELECT id FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    return [get_order(r["id"]) for r in ids.fetchall()]


def set_status(order_id: int, status: str) -> Optional[dict]:
    if status not in STATUSES:
        raise ValueError(status)
    conn = connect()
    with conn:
        conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (status, _now(), order_id))
    return get_order(order_id)


def stats() -> dict:
    conn = connect()
    counts = {key: 0 for key in STATUSES}
    for row in conn.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status"):
        counts[row["status"]] = row["n"]
    today = datetime.now().date().isoformat()
    revenue = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]
    revenue_today = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM orders WHERE status != 'cancelled' AND created_at LIKE ?",
        (today + "%",),
    ).fetchone()[0]
    orders_count = sum(counts.values())
    paid_orders = orders_count - counts["cancelled"]
    top = conn.execute(
        """SELECT i.name, SUM(i.qty) qty FROM order_items i
           JOIN orders o ON o.id = i.order_id AND o.status != 'cancelled'
           GROUP BY i.product_id ORDER BY qty DESC LIMIT 3"""
    ).fetchall()
    return {
        **counts,
        "total": orders_count,
        "revenue": revenue,
        "revenue_today": revenue_today,
        "avg_check": round(revenue / paid_orders) if paid_orders else 0,
        "top": [dict(r) for r in top],
    }
