def _make_user(temp_db, email="cat@example.com"):
    return temp_db.create_user("Cat User", email, "password123")


def test_category_totals_empty_user(temp_db):
    user_id = _make_user(temp_db)
    assert temp_db.get_category_totals(user_id) == []


def test_category_totals_order_and_tiebreak(temp_db, add_expense):
    user_id = _make_user(temp_db)
    add_expense(user_id, 10, "Zeta", "2026-01-01")
    add_expense(user_id, 10, "Alpha", "2026-01-02")
    add_expense(user_id, 50, "Mid", "2026-01-03")
    add_expense(user_id, 30, "Mid", "2026-01-04")
    add_expense(user_id, 5, "Small", "2026-01-05")

    totals = temp_db.get_category_totals(user_id)
    assert [t["name"] for t in totals] == ["Mid", "Alpha", "Zeta", "Small"]
    assert totals[0]["total"] == 80.0


def test_category_totals_ignores_other_users(temp_db, add_expense):
    user_id = _make_user(temp_db)
    other_id = _make_user(temp_db, "other@example.com")
    add_expense(user_id, 10, "Food", "2026-01-01")
    add_expense(other_id, 999, "Bills", "2026-01-01")

    totals = temp_db.get_category_totals(user_id)
    assert totals == [{"name": "Food", "total": 10.0}]


def test_build_categories_empty(client, temp_db):
    import app as app_module

    user_id = _make_user(temp_db)
    assert app_module._build_categories(user_id) == []


def test_build_categories_formats_and_orders(client, temp_db, add_expense):
    import app as app_module

    user_id = _make_user(temp_db)
    add_expense(user_id, 1000, "Bills", "2026-01-01")
    add_expense(user_id, 200.5, "Food", "2026-01-02")

    cats = app_module._build_categories(user_id)
    assert [c["name"] for c in cats] == ["Bills", "Food"]
    assert cats[0]["total"] == "£1,000.00"
    assert cats[1]["total"] == "£200.50"


def test_build_categories_percents_sum_to_100_equal_split(
    client, temp_db, add_expense
):
    import app as app_module

    user_id = _make_user(temp_db)
    for name in ("A", "B", "C"):
        add_expense(user_id, 10, name, "2026-01-01")

    cats = app_module._build_categories(user_id)
    assert [c["name"] for c in cats] == ["A", "B", "C"]
    assert sum(c["percent"] for c in cats) == 100
    assert sorted(c["percent"] for c in cats) == [33, 33, 34]


def test_build_categories_bars_multiple_of_five_and_min(
    client, temp_db, add_expense
):
    import app as app_module

    user_id = _make_user(temp_db)
    add_expense(user_id, 9700, "Big", "2026-01-01")
    add_expense(user_id, 200, "Tiny", "2026-01-02")
    add_expense(user_id, 100, "Medium", "2026-01-03")

    cats = app_module._build_categories(user_id)
    assert sum(c["percent"] for c in cats) == 100
    for cat in cats:
        assert 0 <= cat["bar"] <= 100
        assert cat["bar"] % 5 == 0
        if cat["percent"] > 0:
            assert cat["bar"] >= 5
    tiny = next(c for c in cats if c["name"] == "Tiny")
    assert tiny["percent"] == 2
    assert tiny["bar"] >= 5


def test_build_categories_ignores_other_users(client, temp_db, add_expense):
    import app as app_module

    user_id = _make_user(temp_db)
    other_id = _make_user(temp_db, "other@example.com")
    add_expense(user_id, 20, "Food", "2026-01-01")
    add_expense(other_id, 500, "Bills", "2026-01-01")

    cats = app_module._build_categories(user_id)
    assert [c["name"] for c in cats] == ["Food"]
    assert cats[0]["percent"] == 100
    assert cats[0]["bar"] == 100


def test_build_categories_seeded_demo_user(client, temp_db):
    import app as app_module

    temp_db.seed_db()
    demo = temp_db.get_user_by_email("demo@spendly.com")
    cats = app_module._build_categories(demo["id"])

    names = [c["name"] for c in cats]
    assert len(cats) == 7
    assert names[0] == "Bills"
    assert "Transport" in names
    assert sum(c["percent"] for c in cats) == 100
