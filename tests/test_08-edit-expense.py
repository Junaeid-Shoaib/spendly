"""Tests for Step 8: GET/POST /expenses/<id>/edit (spec: .claude/specs/08-edit-expense.md)."""
import re
from datetime import date, timedelta

import pytest

from database import db

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
TODAY = date.today().isoformat()


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


def _expenses():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()]
    finally:
        conn.close()


def _valid(**overrides):
    data = {
        "amount": "99.00",
        "category": "Bills",
        "date": "2024-03-04",
        "description": "Updated",
    }
    data.update(overrides)
    return data


@pytest.fixture
def user_id(client):
    return _register_and_login(client)


@pytest.fixture
def expense_id(client, user_id, add_expense):
    add_expense(user_id, 12.5, "Food", "2024-01-15", "Lunch")
    return _expenses()[-1]["id"]


@pytest.fixture
def other_expense_id(client, user_id, add_expense):
    """An expense owned by a second user (the logged-in session stays user 1)."""
    client.get("/logout")
    other = _register_and_login(client, email="b@example.com", name="Bob")
    add_expense(other, 50.0, "Health", "2024-02-02", "Bobs secret")
    oid = _expenses()[-1]["id"]
    client.get("/logout")
    client.post("/login", data={"email": "a@example.com", "password": "password123"})
    return oid


def _row(expense_id):
    return next(r for r in _expenses() if r["id"] == expense_id)


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        r = client.get("/expenses/1/edit")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_redirects_and_changes_nothing(self, client, add_expense):
        uid = _register_and_login(client)
        add_expense(uid, 12.5, "Food", "2024-01-15", "Lunch")
        eid = _expenses()[0]["id"]
        client.get("/logout")
        r = client.post(f"/expenses/{eid}/edit", data=_valid())
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        row = _row(eid)
        assert row["amount"] == pytest.approx(12.5)
        assert row["description"] == "Lunch"


class TestGetForm:
    def test_get_own_expense_returns_200(self, client, expense_id):
        assert client.get(f"/expenses/{expense_id}/edit").status_code == 200

    def test_get_prefills_amount_with_two_decimals(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        assert b"12.50" in r.data, "Amount should be shown as 12.50"

    def test_get_prefills_category_selected(self, client, expense_id):
        html = client.get(f"/expenses/{expense_id}/edit").data.decode()
        assert re.search(r'<option value="Food"[^>]*\bselected\b', html), "Food should be selected"
        assert not re.search(r'<option value="Bills"[^>]*\bselected\b', html)

    def test_get_prefills_date_and_description(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        assert b"2024-01-15" in r.data
        assert b"Lunch" in r.data

    def test_get_lists_all_categories(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        for cat in CATEGORIES:
            assert f">{cat}</option>".encode() in r.data, f"Missing category {cat}"

    def test_get_form_action_points_to_edit_url(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        assert f'action="/expenses/{expense_id}/edit"'.encode() in r.data

    def test_get_has_cancel_link_to_profile(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        assert b'href="/profile"' in r.data
        assert b"Cancel" in r.data

    def test_get_has_save_button_and_fields(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/edit")
        assert b"Save changes" in r.data
        for field in (b'name="amount"', b'name="category"', b'name="date"', b'name="description"'):
            assert field in r.data


class TestNotFound:
    def test_get_other_users_expense_404(self, client, other_expense_id):
        assert client.get(f"/expenses/{other_expense_id}/edit").status_code == 404

    def test_get_nonexistent_id_404(self, client, user_id):
        assert client.get("/expenses/9999/edit").status_code == 404

    def test_post_other_users_expense_404_and_unchanged(self, client, other_expense_id):
        before = _row(other_expense_id)
        r = client.post(f"/expenses/{other_expense_id}/edit", data=_valid())
        assert r.status_code == 404
        assert _row(other_expense_id) == before

    def test_post_nonexistent_id_404(self, client, user_id):
        r = client.post("/expenses/9999/edit", data=_valid())
        assert r.status_code == 404
        assert _expenses() == []

    def test_other_users_expense_description_not_leaked(self, client, other_expense_id):
        r = client.get(f"/expenses/{other_expense_id}/edit")
        assert b"Bobs secret" not in r.data


class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid())
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/profile")

    def test_valid_post_updates_db(self, client, expense_id, user_id):
        client.post(f"/expenses/{expense_id}/edit", data=_valid())
        rows = _expenses()
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == expense_id
        assert row["user_id"] == user_id
        assert row["amount"] == pytest.approx(99.0)
        assert row["category"] == "Bills"
        assert row["date"] == "2024-03-04"
        assert row["description"] == "Updated"

    def test_profile_shows_new_values(self, client, expense_id):
        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid(amount="77.25", description="UniqueNewDesc"),
        )
        r = client.get("/profile")
        assert b"UniqueNewDesc" in r.data
        assert b"77.25" in r.data
        assert b"Lunch" not in r.data, "Old description should be gone"

    def test_profile_stats_recalculated(self, client, expense_id):
        client.post(f"/expenses/{expense_id}/edit", data=_valid(amount="40.00"))
        r = client.get("/profile")
        assert b"40.00" in r.data

    @pytest.mark.parametrize("desc", ["", "   "])
    def test_blank_description_stored_null(self, client, expense_id, desc):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(description=desc))
        assert r.status_code == 302
        assert _row(expense_id)["description"] is None

    def test_blank_description_shown_as_dash_on_profile(self, client, expense_id):
        client.post(f"/expenses/{expense_id}/edit", data=_valid(description=""))
        r = client.get("/profile")
        assert "—".encode() in r.data

    def test_other_expenses_untouched(self, client, user_id, add_expense, expense_id):
        add_expense(user_id, 5.0, "Transport", "2024-02-01", "Bus")
        bus = next(r for r in _expenses() if r["description"] == "Bus")
        client.post(f"/expenses/{expense_id}/edit", data=_valid())
        assert _row(bus["id"]) == bus

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_accepted(self, client, expense_id, category):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(category=category))
        assert r.status_code == 302
        assert _row(expense_id)["category"] == category

    def test_description_200_chars_accepted(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(description="x" * 200))
        assert r.status_code == 302
        assert len(_row(expense_id)["description"]) == 200

    def test_today_date_accepted(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(date=TODAY))
        assert r.status_code == 302
        assert _row(expense_id)["date"] == TODAY


class TestValidationErrors:
    @pytest.mark.parametrize("amount", ["", "0", "-5", "abc", "nan", "1.234"])
    def test_invalid_amount_rejected(self, client, expense_id, amount):
        before = _row(expense_id)
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(amount=amount))
        assert r.status_code == 400, f"amount {amount!r} should be rejected"
        assert _row(expense_id) == before

    def test_invalid_category_rejected(self, client, expense_id):
        before = _row(expense_id)
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(category="Hacking"))
        assert r.status_code == 400
        assert _row(expense_id) == before

    @pytest.mark.parametrize("bad_date", ["", "not-a-date", "2024-02-30", "01/02/2024"])
    def test_invalid_date_rejected(self, client, expense_id, bad_date):
        before = _row(expense_id)
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(date=bad_date))
        assert r.status_code == 400
        assert _row(expense_id) == before

    def test_future_date_rejected(self, client, expense_id):
        before = _row(expense_id)
        future = (date.today() + timedelta(days=2)).isoformat()
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(date=future))
        assert r.status_code == 400
        assert _row(expense_id) == before

    def test_description_201_chars_rejected(self, client, expense_id):
        before = _row(expense_id)
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(description="x" * 201))
        assert r.status_code == 400
        assert _row(expense_id) == before

    def test_error_message_shown(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(amount="0"))
        assert r.status_code == 400
        assert b'role="alert"' in r.data or b"error" in r.data.lower()

    def test_error_keeps_submitted_values(self, client, expense_id):
        r = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid(amount="-3", category="Health", date="2023-05-06",
                        description="KeepMeText"),
        )
        assert r.status_code == 400
        html = r.data.decode()
        assert "-3" in html
        assert "2023-05-06" in html
        assert "KeepMeText" in html
        assert re.search(r'<option value="Health"[^>]*\bselected\b', html)

    def test_error_response_form_action_still_correct(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(amount=""))
        assert f'action="/expenses/{expense_id}/edit"'.encode() in r.data


class TestOwnership:
    def test_form_user_id_is_ignored(self, client, expense_id, user_id):
        r = client.post(f"/expenses/{expense_id}/edit",
                        data=_valid(user_id=str(user_id + 100)))
        assert r.status_code == 302
        assert _row(expense_id)["user_id"] == user_id

    def test_sql_injection_in_description_stored_literally(self, client, expense_id):
        payload = "'); DROP TABLE expenses;--"
        r = client.post(f"/expenses/{expense_id}/edit", data=_valid(description=payload))
        assert r.status_code == 302
        assert _row(expense_id)["description"] == payload


class TestProfileIntegration:
    def test_profile_rows_have_edit_link(self, client, expense_id):
        r = client.get("/profile")
        assert f'href="/expenses/{expense_id}/edit"'.encode() in r.data

    def test_each_row_links_to_its_own_id(self, client, user_id, add_expense):
        add_expense(user_id, 1.0, "Food", "2024-01-01", "One")
        add_expense(user_id, 2.0, "Food", "2024-01-02", "Two")
        r = client.get("/profile")
        for row in _expenses():
            assert f'href="/expenses/{row["id"]}/edit"'.encode() in r.data

    def test_edit_link_target_opens(self, client, expense_id):
        assert client.get(f"/expenses/{expense_id}/edit").status_code == 200


class TestDeleteStubUnchanged:
    def test_delete_stub_returns_stub_text(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/delete")
        assert r.status_code == 200
        assert b"Delete expense" in r.data
        assert b"Step 9" in r.data

    def test_delete_stub_does_not_delete(self, client, expense_id):
        client.get(f"/expenses/{expense_id}/delete")
        assert len(_expenses()) == 1


class TestDbHelpers:
    def test_get_expense_by_id_returns_dict_for_owner(self, client, user_id, expense_id):
        exp = db.get_expense_by_id(expense_id, user_id)
        assert isinstance(exp, dict)
        assert exp["id"] == expense_id
        assert isinstance(exp["amount"], float)
        assert exp["amount"] == pytest.approx(12.5)
        assert exp["category"] == "Food"
        assert exp["date"] == "2024-01-15"
        assert exp["description"] == "Lunch"

    def test_get_expense_by_id_none_for_other_user(self, client, user_id, expense_id):
        assert db.get_expense_by_id(expense_id, user_id + 100) is None

    def test_get_expense_by_id_none_for_missing(self, client, user_id):
        assert db.get_expense_by_id(9999, user_id) is None

    def test_update_expense_owner_returns_true_and_updates(self, client, user_id, expense_id):
        assert db.update_expense(expense_id, user_id, 3.5, "Other", "2024-05-05", "New") is True
        row = _row(expense_id)
        assert row["amount"] == pytest.approx(3.5)
        assert row["category"] == "Other"
        assert row["date"] == "2024-05-05"
        assert row["description"] == "New"

    @pytest.mark.parametrize("blank", [None, ""])
    def test_update_expense_blank_description_null(self, client, user_id, expense_id, blank):
        assert db.update_expense(expense_id, user_id, 3.5, "Other", "2024-05-05", blank) is True
        assert _row(expense_id)["description"] is None

    def test_update_expense_non_owner_returns_false_and_unchanged(self, client, user_id, expense_id):
        before = _row(expense_id)
        assert db.update_expense(expense_id, user_id + 100, 3.5, "Other", "2024-05-05", "X") is False
        assert _row(expense_id) == before

    def test_update_expense_missing_returns_false(self, client, user_id):
        assert db.update_expense(9999, user_id, 3.5, "Other", "2024-05-05", "X") is False

    def test_get_recent_expenses_includes_int_id(self, client, user_id, expense_id):
        rows = db.get_recent_expenses(user_id)
        assert rows, "Expected at least one recent expense"
        assert isinstance(rows[0]["id"], int)
        assert rows[0]["id"] == expense_id
