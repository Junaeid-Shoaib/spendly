"""Tests for Step 9: GET/POST /expenses/<id>/delete (spec: .claude/specs/09-delete-expense.md)."""
import pytest

from database import db


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


@pytest.fixture
def user_id(client):
    return _register_and_login(client)


@pytest.fixture
def expense_id(client, user_id, add_expense):
    add_expense(user_id, 12.5, "Food", "2024-01-15", "Lunch")
    return _expenses()[-1]["id"]


@pytest.fixture
def other_expense_id(client, add_expense):
    """An expense owned by a second user, created directly in the DB so it
    works regardless of who is logged in."""
    other_id = db.create_user("Bob", "b@example.com", "password123")
    add_expense(other_id, 99.0, "Bills", "2024-02-01", "Bobs bill")
    return _expenses()[-1]["id"]


# ------------------------------------------------------------------ #
# DB helper                                                           #
# ------------------------------------------------------------------ #

def test_helper_deletes_owned_expense(user_id, expense_id):
    assert db.delete_expense(expense_id, user_id) is True
    assert _expenses() == []


def test_helper_wrong_owner_returns_false(user_id, expense_id):
    assert db.delete_expense(expense_id, user_id + 100) is False
    assert len(_expenses()) == 1


def test_helper_missing_id_returns_false(user_id):
    assert db.delete_expense(9999, user_id) is False


def test_helper_second_delete_returns_false(user_id, expense_id):
    assert db.delete_expense(expense_id, user_id) is True
    assert db.delete_expense(expense_id, user_id) is False


def test_helper_leaves_other_rows(user_id, expense_id, add_expense):
    add_expense(user_id, 5.0, "Other", "2024-01-16", "Keep")
    db.delete_expense(expense_id, user_id)
    rows = _expenses()
    assert len(rows) == 1
    assert rows[0]["description"] == "Keep"


# ------------------------------------------------------------------ #
# Logged out                                                          #
# ------------------------------------------------------------------ #

def test_logged_out_get_redirects_to_login(client):
    response = client.get("/expenses/1/delete")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_out_post_redirects_and_deletes_nothing(client, add_expense):
    owner_id = _register_and_login(client, email="o@example.com", name="Owner")
    add_expense(owner_id, 10.0, "Food", "2024-01-01", "Mine")
    expense = _expenses()[-1]["id"]
    client.get("/logout")

    response = client.post(f"/expenses/{expense}/delete")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert len(_expenses()) == 1


# ------------------------------------------------------------------ #
# Confirmation page (GET)                                             #
# ------------------------------------------------------------------ #

def test_get_shows_confirmation_details(client, expense_id):
    response = client.get(f"/expenses/{expense_id}/delete")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "2024-01-15" in body
    assert "Food" in body
    assert "Lunch" in body
    assert "£12.50" in body
    assert 'method="POST"' in body
    assert f'action="/expenses/{expense_id}/delete"' in body
    assert 'href="/profile"' in body


def test_get_blank_description_shows_dash(client, user_id, add_expense):
    add_expense(user_id, 3.0, "Other", "2024-01-02", None)
    expense = _expenses()[-1]["id"]
    body = client.get(f"/expenses/{expense}/delete").get_data(as_text=True)
    assert "—" in body


def test_get_does_not_delete(client, expense_id):
    client.get(f"/expenses/{expense_id}/delete")
    assert len(_expenses()) == 1
    assert "Lunch" in client.get("/profile").get_data(as_text=True)


def test_get_escapes_description(client, user_id, add_expense):
    add_expense(user_id, 3.0, "Other", "2024-01-02", "<script>alert(1)</script>")
    expense = _expenses()[-1]["id"]
    body = client.get(f"/expenses/{expense}/delete").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


# ------------------------------------------------------------------ #
# Not owned / missing                                                 #
# ------------------------------------------------------------------ #

def test_get_other_users_expense_404(client, user_id, other_expense_id):
    assert client.get(f"/expenses/{other_expense_id}/delete").status_code == 404


def test_post_other_users_expense_404_and_kept(client, user_id, other_expense_id):
    assert client.post(f"/expenses/{other_expense_id}/delete").status_code == 404
    assert any(e["id"] == other_expense_id for e in _expenses())


def test_get_and_post_missing_id_404(client, user_id):
    assert client.get("/expenses/9999/delete").status_code == 404
    assert client.post("/expenses/9999/delete").status_code == 404


def test_non_integer_id_404(client, user_id):
    assert client.get("/expenses/abc/delete").status_code == 404


# ------------------------------------------------------------------ #
# POST success                                                        #
# ------------------------------------------------------------------ #

def test_post_deletes_and_redirects_to_profile(client, expense_id):
    response = client.post(f"/expenses/{expense_id}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert _expenses() == []


def test_post_updates_profile_stats(client, user_id, expense_id, add_expense):
    add_expense(user_id, 7.5, "Transport", "2024-01-20", "Bus")
    client.post(f"/expenses/{expense_id}/delete")
    body = client.get("/profile").get_data(as_text=True)
    assert "Lunch" not in body
    assert "Bus" in body
    assert "£7.50" in body


def test_second_post_404(client, expense_id):
    client.post(f"/expenses/{expense_id}/delete")
    assert client.post(f"/expenses/{expense_id}/delete").status_code == 404


def test_deleting_only_expense_shows_empty_state(client, expense_id):
    client.post(f"/expenses/{expense_id}/delete")
    response = client.get("/profile")
    assert response.status_code == 200
    assert "No transactions yet." in response.get_data(as_text=True)


def test_post_ignores_user_id_form_field(client, user_id, other_expense_id):
    response = client.post(
        f"/expenses/{other_expense_id}/delete", data={"user_id": "2"}
    )
    assert response.status_code == 404
    assert any(e["id"] == other_expense_id for e in _expenses())


# ------------------------------------------------------------------ #
# Profile link                                                        #
# ------------------------------------------------------------------ #

def test_profile_has_delete_link(client, expense_id):
    body = client.get("/profile").get_data(as_text=True)
    assert f'href="/expenses/{expense_id}/delete"' in body
