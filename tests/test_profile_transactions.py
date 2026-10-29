import pytest


@pytest.fixture
def app_module(client):
    import app as app_module

    return app_module


def _user(temp_db, email="a@example.com"):
    return temp_db.create_user("Test", email, "password123")


def test_get_recent_expenses_empty(temp_db):
    user_id = _user(temp_db)
    assert temp_db.get_recent_expenses(user_id) == []


def test_get_recent_expenses_shape_and_order(temp_db, add_expense):
    user_id = _user(temp_db)
    add_expense(user_id, 10, "Food", "2026-01-01", "old")
    add_expense(user_id, 20, "Bills", "2026-03-01", "first")
    add_expense(user_id, 30, "Transport", "2026-03-01", "second")

    rows = temp_db.get_recent_expenses(user_id)

    assert [r["description"] for r in rows] == ["second", "first", "old"]
    assert rows[0] == {
        "date": "2026-03-01",
        "description": "second",
        "category": "Transport",
        "amount": 30.0,
    }


def test_get_recent_expenses_limit(temp_db, add_expense):
    user_id = _user(temp_db)
    for day in range(1, 9):
        add_expense(user_id, day, "Food", f"2026-02-{day:02d}")

    rows = temp_db.get_recent_expenses(user_id)

    assert len(rows) == 5
    assert rows[0]["date"] == "2026-02-08"
    assert len(temp_db.get_recent_expenses(user_id, limit=2)) == 2


def test_get_recent_expenses_ignores_other_users(temp_db, add_expense):
    user_a = _user(temp_db, "a@example.com")
    user_b = _user(temp_db, "b@example.com")
    add_expense(user_b, 99, "Food", "2026-02-01", "not mine")

    assert temp_db.get_recent_expenses(user_a) == []
    assert len(temp_db.get_recent_expenses(user_b)) == 1


def test_build_transactions_empty(temp_db, app_module):
    user_id = _user(temp_db)
    assert app_module._build_transactions(user_id) == []


def test_build_transactions_format(temp_db, app_module, add_expense):
    user_id = _user(temp_db)
    add_expense(user_id, 1299, "Shopping", "2026-04-02", "Laptop")

    assert app_module._build_transactions(user_id) == [
        {
            "date": "2026-04-02",
            "description": "Laptop",
            "category": "Shopping",
            "amount": "£1,299.00",
        }
    ]


def test_build_transactions_missing_description(temp_db, app_module, add_expense):
    user_id = _user(temp_db)
    add_expense(user_id, 5, "Food", "2026-04-03", None)
    add_expense(user_id, 6, "Food", "2026-04-02", "   ")

    rows = app_module._build_transactions(user_id)

    assert [r["description"] for r in rows] == ["—", "—"]


def test_build_transactions_order_limit_and_scope(temp_db, app_module, add_expense):
    user_a = _user(temp_db, "a@example.com")
    user_b = _user(temp_db, "b@example.com")
    for day in range(1, 8):
        add_expense(user_a, day, "Food", f"2026-05-{day:02d}", f"a{day}")
    add_expense(user_b, 500, "Bills", "2026-06-01", "b")

    rows = app_module._build_transactions(user_a)

    assert [r["description"] for r in rows] == ["a7", "a6", "a5", "a4", "a3"]
