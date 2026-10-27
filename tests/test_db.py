import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_get_db_row_factory_and_fk_pragma(temp_db):
    conn = temp_db.get_db()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        temp_db.seed_db()
        row = conn.execute("SELECT * FROM users").fetchone()
        assert row["email"] == "demo@spendly.com"
    finally:
        conn.close()


def test_init_db_creates_tables_and_is_repeatable(temp_db):
    temp_db.init_db()
    conn = temp_db.get_db()
    try:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert {"users", "expenses"} <= names


def test_seed_inserts_demo_user_and_expenses(temp_db):
    temp_db.seed_db()
    conn = temp_db.get_db()
    try:
        assert _count(conn, "users") == 1
        assert _count(conn, "expenses") == 8
        categories = {
            r[0] for r in conn.execute("SELECT DISTINCT category FROM expenses")
        }
    finally:
        conn.close()
    assert categories == set(temp_db.CATEGORIES)


def test_seed_is_idempotent(temp_db):
    temp_db.seed_db()
    temp_db.seed_db()
    conn = temp_db.get_db()
    try:
        assert _count(conn, "users") == 1
        assert _count(conn, "expenses") == 8
    finally:
        conn.close()


def test_seed_password_is_hashed(temp_db):
    temp_db.seed_db()
    conn = temp_db.get_db()
    try:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    finally:
        conn.close()
    assert stored != "demo123"
    assert check_password_hash(stored, "demo123")


def test_seed_dates_valid_and_in_current_month(temp_db):
    temp_db.seed_db()
    today = date.today()
    conn = temp_db.get_db()
    try:
        dates = [r[0] for r in conn.execute("SELECT date FROM expenses")]
    finally:
        conn.close()
    for value in dates:
        parsed = date.fromisoformat(value)
        assert (parsed.year, parsed.month) == (today.year, today.month)
        assert parsed <= today


def test_duplicate_email_rejected(temp_db):
    temp_db.seed_db()
    conn = temp_db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Other", "demo@spendly.com", "x"),
            )
    finally:
        conn.close()


def test_expense_invalid_user_id_rejected(temp_db):
    conn = temp_db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) "
                "VALUES (?, ?, ?, ?)",
                (999, 1.0, "Food", "2026-10-01"),
            )
    finally:
        conn.close()


def test_expense_requires_amount(temp_db):
    temp_db.seed_db()
    conn = temp_db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) "
                "VALUES (?, ?, ?, ?)",
                (1, None, "Food", "2026-10-01"),
            )
    finally:
        conn.close()
