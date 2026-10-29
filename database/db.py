import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = ?",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=5):
    """Return the user's newest expenses as a list of dicts.

    Keys: date (raw ISO str), description (str or None), category, amount (float).
    Ordered by date DESC, id DESC.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_expense_stats(user_id):
    """Return {"total": float, "count": int, "top_category": str or None}.

    top_category is the category with the highest total; ties are broken
    alphabetically by category name.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "total": float(row["total"]),
        "count": row["count"],
        "top_category": top["category"] if top else None,
    }


def get_category_totals(user_id):
    """Return [{"name": str, "total": float}], highest total first.

    Ties are broken alphabetically by category name.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY SUM(amount) DESC, category ASC",
            (user_id,),
        ).fetchall()
        return [{"name": row["category"], "total": float(row["total"])} for row in rows]
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cursor.lastrowid

        today = date.today()

        def day(d):
            return date(today.year, today.month, min(d, today.day)).isoformat()

        expenses = [
            (user_id, 450.00, "Food", day(1), "Weekly groceries"),
            (user_id, 120.50, "Transport", day(3), "Metro card top-up"),
            (user_id, 1800.00, "Bills", day(5), "Electricity bill"),
            (user_id, 650.00, "Health", day(8), "Pharmacy"),
            (user_id, 399.99, "Entertainment", day(12), "Movie night"),
            (user_id, 1299.00, "Shopping", day(15), "New headphones"),
            (user_id, 75.25, "Other", day(20), None),
            (user_id, 220.00, "Food", day(25), "Dinner out"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
