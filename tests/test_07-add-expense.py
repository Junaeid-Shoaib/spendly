"""Tests for Step 7: GET/POST /expenses/add (spec: .claude/specs/07-add-expense.md)."""
from datetime import date, timedelta

import pytest

from database import db

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def _register_and_login(client, email="a@example.com", name="Alice"):
    client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    client.post("/login", data={"email": email, "password": "password123"})
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()
    return row["id"]


@pytest.fixture
def user_id(client):
    return _register_and_login(client)


def _expenses():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()]
    finally:
        conn.close()


def _valid(**overrides):
    data = {
        "amount": "12.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Lunch",
    }
    data.update(overrides)
    return data


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        r = client.get("/expenses/add")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_redirects_and_saves_nothing(self, client):
        r = client.post("/expenses/add", data=_valid())
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        assert _expenses() == []


class TestGetForm:
    def test_get_logged_in_returns_200_with_form(self, client, user_id):
        r = client.get("/expenses/add")
        assert r.status_code == 200
        for field in (b'name="amount"', b'name="category"', b'name="date"', b'name="description"'):
            assert field in r.data, f"Missing {field!r} in form"

    def test_get_prefills_today_date(self, client, user_id):
        r = client.get("/expenses/add")
        assert date.today().isoformat().encode() in r.data

    def test_get_lists_all_seven_categories(self, client, user_id):
        r = client.get("/expenses/add")
        for cat in CATEGORIES:
            assert f">{cat}</option>".encode() in r.data, f"Missing category {cat}"

    def test_get_has_cancel_link_to_profile(self, client, user_id):
        r = client.get("/expenses/add")
        assert b'href="/profile"' in r.data

    def test_get_extends_base_layout(self, client, user_id):
        r = client.get("/expenses/add")
        assert b"Spendly" in r.data


class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, client, user_id):
        r = client.post("/expenses/add", data=_valid())
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/profile")

    def test_valid_post_creates_row_with_correct_values(self, client, user_id):
        client.post("/expenses/add", data=_valid(amount="45.99", category="Bills",
                                                  description="Electricity"))
        rows = _expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id
        assert rows[0]["amount"] == pytest.approx(45.99)
        assert rows[0]["category"] == "Bills"
        assert rows[0]["date"] == date.today().isoformat()
        assert rows[0]["description"] == "Electricity"

    def test_expense_appears_on_profile(self, client, user_id):
        client.post("/expenses/add", data=_valid(amount="77.25", description="UniqueDesc"))
        r = client.get("/profile")
        assert b"UniqueDesc" in r.data
        assert b"77.25" in r.data

    def test_profile_stats_reflect_new_expenses(self, client, user_id):
        client.post("/expenses/add", data=_valid(amount="10.00", category="Food"))
        client.post("/expenses/add", data=_valid(amount="20.00", category="Transport"))
        r = client.get("/profile")
        assert b"30.00" in r.data, "Total spent should be 30.00"
        assert b"Food" in r.data and b"Transport" in r.data

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_is_accepted(self, client, user_id, category):
        r = client.post("/expenses/add", data=_valid(category=category))
        assert r.status_code == 302
        assert _expenses()[0]["category"] == category

    @pytest.mark.parametrize("amount", ["5", "5.5", "5.55", "0.01", "1000000"])
    def test_valid_amounts_accepted(self, client, user_id, amount):
        r = client.post("/expenses/add", data=_valid(amount=amount))
        assert r.status_code == 302, f"amount {amount} should be valid"
        assert _expenses()[0]["amount"] == pytest.approx(float(amount))

    def test_past_date_accepted(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(date="2020-01-15"))
        assert r.status_code == 302
        assert _expenses()[0]["date"] == "2020-01-15"

    def test_today_date_accepted(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(date=date.today().isoformat()))
        assert r.status_code == 302

    def test_description_max_200_chars_accepted(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(description="x" * 200))
        assert r.status_code == 302
        assert len(_expenses()[0]["description"]) == 200


class TestDescription:
    @pytest.mark.parametrize("desc", ["", "   "])
    def test_blank_description_saved_as_null(self, client, user_id, desc):
        r = client.post("/expenses/add", data=_valid(description=desc))
        assert r.status_code == 302
        assert _expenses()[0]["description"] is None

    def test_missing_description_field_saved(self, client, user_id):
        data = _valid()
        del data["description"]
        r = client.post("/expenses/add", data=data)
        assert r.status_code == 302
        assert _expenses()[0]["description"] is None

    def test_blank_description_shows_dash_on_profile(self, client, user_id):
        client.post("/expenses/add", data=_valid(description=""))
        r = client.get("/profile")
        assert "—".encode() in r.data

    def test_description_is_stripped(self, client, user_id):
        client.post("/expenses/add", data=_valid(description="  padded  "))
        assert _expenses()[0]["description"] == "padded"

    def test_description_over_200_chars_rejected(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(description="x" * 201))
        assert r.status_code == 400
        assert _expenses() == []


class TestValidationErrors:
    @pytest.mark.parametrize(
        "amount",
        ["", "0", "0.00", "-5", "-0.01", "abc", "nan", "NaN", "inf", "-inf", "1.234", "5.001"],
    )
    def test_invalid_amount_rejected(self, client, user_id, amount):
        r = client.post("/expenses/add", data=_valid(amount=amount))
        assert r.status_code == 400, f"amount {amount!r} should be rejected"
        assert _expenses() == []

    def test_missing_amount_field_rejected(self, client, user_id):
        data = _valid()
        del data["amount"]
        r = client.post("/expenses/add", data=data)
        assert r.status_code == 400
        assert _expenses() == []

    @pytest.mark.parametrize("category", ["", "Hacking", "food", "FOOD", "Food; DROP TABLE expenses"])
    def test_invalid_category_rejected(self, client, user_id, category):
        r = client.post("/expenses/add", data=_valid(category=category))
        assert r.status_code == 400
        assert _expenses() == []

    def test_missing_category_field_rejected(self, client, user_id):
        data = _valid()
        del data["category"]
        r = client.post("/expenses/add", data=data)
        assert r.status_code == 400
        assert _expenses() == []

    @pytest.mark.parametrize(
        "bad_date", ["", "not-a-date", "2024-13-01", "2024-02-30", "01/02/2024", "2024/01/02"]
    )
    def test_invalid_date_rejected(self, client, user_id, bad_date):
        r = client.post("/expenses/add", data=_valid(date=bad_date))
        assert r.status_code == 400, f"date {bad_date!r} should be rejected"
        assert _expenses() == []

    def test_missing_date_field_rejected(self, client, user_id):
        data = _valid()
        del data["date"]
        r = client.post("/expenses/add", data=data)
        assert r.status_code == 400
        assert _expenses() == []

    def test_future_date_rejected(self, client, user_id):
        future = (date.today() + timedelta(days=2)).isoformat()
        r = client.post("/expenses/add", data=_valid(date=future))
        assert r.status_code == 400
        assert _expenses() == []

    def test_error_response_shows_error_message_area(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(amount="0"))
        assert r.status_code == 400
        assert b"error" in r.data.lower(), "Expected an error message in the page"

    def test_error_keeps_submitted_values(self, client, user_id):
        r = client.post(
            "/expenses/add",
            data=_valid(amount="-3", category="Health", date="2023-05-06",
                        description="KeepMeText"),
        )
        assert r.status_code == 400
        assert b"-3" in r.data
        assert b"2023-05-06" in r.data
        assert b"KeepMeText" in r.data
        assert b'value="Health" selected' in r.data or b"selected" in r.data

    def test_error_response_still_lists_categories(self, client, user_id):
        r = client.post("/expenses/add", data=_valid(amount=""))
        for cat in CATEGORIES:
            assert cat.encode() in r.data

    def test_sql_injection_in_description_stored_literally(self, client, user_id):
        payload = "'); DROP TABLE expenses;--"
        r = client.post("/expenses/add", data=_valid(description=payload))
        assert r.status_code == 302
        rows = _expenses()
        assert len(rows) == 1
        assert rows[0]["description"] == payload


class TestOwnership:
    def test_form_user_id_is_ignored(self, client, user_id):
        other_id = user_id + 100
        r = client.post("/expenses/add", data=_valid(user_id=str(other_id)))
        assert r.status_code == 302
        rows = _expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id, "Expense must belong to the session user"

    def test_expense_belongs_to_logged_in_user_when_multiple_users(self, client):
        _register_and_login(client, email="first@example.com", name="First")
        client.get("/logout")
        second =_register_and_login(client, email="second@example.com", name="Second")
        client.post("/expenses/add", data=_valid())
        assert _expenses()[0]["user_id"] == second


class TestCreateExpenseHelper:
    def test_create_expense_inserts_and_returns_lastrowid(self, client, user_id):
        new_id = db.create_expense(user_id, 9.99, "Food", "2024-01-01", "Snack")
        assert isinstance(new_id, int)
        rows = _expenses()
        assert rows[0]["id"] == new_id
        assert rows[0]["description"] == "Snack"

    @pytest.mark.parametrize("blank", [None, ""])
    def test_create_expense_blank_description_stored_as_none(self, client, user_id, blank):
        db.create_expense(user_id, 1.0, "Other", "2024-01-01", blank)
        assert _expenses()[0]["description"] is None


class TestProfileIntegration:
    def test_profile_has_add_expense_link(self, client, user_id):
        r = client.get("/profile")
        assert b'href="/expenses/add"' in r.data

    def test_add_expense_link_target_works(self, client, user_id):
        assert client.get("/expenses/add").status_code == 200


class TestOtherStubsUnchanged:
    def test_edit_is_no_longer_a_stub(self, client, user_id):
        # Step 8 implemented edit; an unknown id now 404s (see test_08).
        r = client.get("/expenses/1/edit")
        assert r.status_code == 404
        assert _expenses() == []

    def test_delete_stub_does_not_delete(self, client, user_id):
        db.create_expense(user_id, 5.0, "Food", "2024-01-01", None)
        client.get("/expenses/1/delete")
        assert len(_expenses()) == 1, "Delete stub must not delete anything yet"
