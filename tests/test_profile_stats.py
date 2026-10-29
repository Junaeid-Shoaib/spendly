import pytest


@pytest.fixture
def app_module(client):
    import app as app_module

    return app_module


def _new_user(temp_db, name="Test User", email="test@example.com"):
    return temp_db.create_user(name, email, "password123")


def test_stats_empty_user(temp_db, app_module):
    user_id = _new_user(temp_db)

    assert temp_db.get_expense_stats(user_id) == {
        "total": 0.0,
        "count": 0,
        "top_category": None,
    }
    assert app_module._build_stats(user_id) == {
        "total_spent": "£0.00",
        "transaction_count": 0,
        "top_category": "—",
    }


def test_stats_user_with_data(temp_db, app_module, add_expense):
    user_id = _new_user(temp_db)
    add_expense(user_id, 1200.50, "Bills", "2026-01-01")
    add_expense(user_id, 30.25, "Food", "2026-01-02")
    add_expense(user_id, 20.00, "Food", "2026-01-03")

    stats = temp_db.get_expense_stats(user_id)
    assert stats["total"] == pytest.approx(1250.75)
    assert stats["count"] == 3
    assert stats["top_category"] == "Bills"
    assert app_module._build_stats(user_id) == {
        "total_spent": "£1,250.75",
        "transaction_count": 3,
        "top_category": "Bills",
    }


def test_stats_seeded_demo_user(temp_db, app_module):
    temp_db.seed_db()
    demo = temp_db.get_user_by_email("demo@spendly.com")

    assert app_module._build_stats(demo["id"]) == {
        "total_spent": "£5,014.74",
        "transaction_count": 8,
        "top_category": "Bills",
    }


def test_stats_tie_resolves_alphabetically(temp_db, add_expense):
    user_id = _new_user(temp_db)
    add_expense(user_id, 50.00, "Travel", "2026-01-01")
    add_expense(user_id, 50.00, "Food", "2026-01-02")

    assert temp_db.get_expense_stats(user_id)["top_category"] == "Food"


def test_stats_ignore_other_users(temp_db, app_module, add_expense):
    user_id = _new_user(temp_db)
    other_id = _new_user(temp_db, "Other", "other@example.com")
    add_expense(user_id, 10.00, "Food", "2026-01-01")
    add_expense(other_id, 999.00, "Shopping", "2026-01-02")
    add_expense(other_id, 1.00, "Shopping", "2026-01-03")

    stats = temp_db.get_expense_stats(user_id)
    assert stats == {"total": 10.0, "count": 1, "top_category": "Food"}
    assert app_module._build_stats(user_id)["total_spent"] == "£10.00"
