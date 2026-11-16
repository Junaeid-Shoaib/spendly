"""Tests for Step 9: GET/POST /expenses/<id>/delete (spec: .claude/specs/09-delete-expense.md)."""
import pytest

from database import db


def _login(client, email="a@example.com"):
    return client.post("/login", data={"email": email, "password": "password123"})


def _expenses():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()]
    finally:
        conn.close()


def _ids():
    return [r["id"] for r in _expenses()]


@pytest.fixture
def user_id(client):
    uid = db.create_user("Alice", "a@example.com", "password123")
    _login(client)
    return uid


@pytest.fixture
def expense_id(client, user_id, add_expense):
    add_expense(user_id, 12.5, "Food", "2024-01-15", "Lunch special")
    return _expenses()[-1]["id"]


@pytest.fixture
def other_expense_id(client, user_id, add_expense):
    other = db.create_user("Bob", "b@example.com", "password123")
    add_expense(other, 50.0, "Health", "2024-02-02", "Bobs secret")
    return _expenses()[-1]["id"]


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        r = client.get("/expenses/1/delete")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_redirects_and_deletes_nothing(self, client, add_expense):
        uid = db.create_user("Alice", "a@example.com", "password123")
        add_expense(uid, 10, "Food", "2024-01-01", "x")
        eid = _expenses()[0]["id"]
        r = client.post(f"/expenses/{eid}/delete")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        assert eid in _ids(), "Logged-out POST must not delete"


class TestConfirmPage:
    def test_get_shows_expense_details(self, client, expense_id):
        r = client.get(f"/expenses/{expense_id}/delete")
        assert r.status_code == 200
        body = r.data.decode()
        assert "Delete this expense?" in body
        assert "Food" in body
        assert "Lunch special" in body
        assert "2024-01-15" in body
        assert "12.50" in body, "Amount should be shown"
        assert "Cancel" in body
        assert "Delete expense" in body

    def test_get_has_post_form_to_delete_url(self, client, expense_id):
        body = client.get(f"/expenses/{expense_id}/delete").data.decode().lower()
        assert 'method="post"' in body
        assert f"/expenses/{expense_id}/delete" in body

    def test_get_does_not_delete(self, client, expense_id):
        client.get(f"/expenses/{expense_id}/delete")
        assert expense_id in _ids(), "GET must never delete"
        r = client.get("/profile")
        assert b"Lunch special" in r.data

    def test_get_without_description_shows_dash(self, client, user_id, add_expense):
        add_expense(user_id, 5, "Other", "2024-03-03", None)
        eid = _expenses()[-1]["id"]
        r = client.get(f"/expenses/{eid}/delete")
        assert r.status_code == 200
        assert "—" in r.data.decode()

    def test_cancel_link_points_to_profile(self, client, expense_id):
        body = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert 'href="/profile"' in body
        assert expense_id in _ids()


class TestNotFound:
    def test_get_missing_id_404(self, client, user_id):
        assert client.get("/expenses/99999/delete").status_code == 404

    def test_post_missing_id_404(self, client, user_id):
        assert client.post("/expenses/99999/delete").status_code == 404

    def test_get_other_users_expense_404(self, client, other_expense_id):
        r = client.get(f"/expenses/{other_expense_id}/delete")
        assert r.status_code == 404
        assert b"Bobs secret" not in r.data

    def test_post_other_users_expense_404_and_kept(self, client, other_expense_id):
        r = client.post(f"/expenses/{other_expense_id}/delete")
        assert r.status_code == 404
        assert other_expense_id in _ids(), "Non-owned expense must remain"

    def test_user_id_in_form_cannot_override_ownership(self, client, other_expense_id):
        other = [r for r in _expenses() if r["id"] == other_expense_id][0]["user_id"]
        r = client.post(f"/expenses/{other_expense_id}/delete", data={"user_id": str(other)})
        assert r.status_code == 404
        assert other_expense_id in _ids()


class TestDelete:
    def test_post_redirects_to_profile(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/delete")
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/profile")

    def test_post_removes_row_from_db(self, client, expense_id):
        client.post(f"/expenses/{expense_id}/delete")
        assert expense_id not in _ids()

    def test_post_only_removes_target_expense(self, client, user_id, add_expense):
        add_expense(user_id, 1, "Food", "2024-01-01", "keepme")
        add_expense(user_id, 2, "Bills", "2024-01-02", "removeme")
        keep, remove = _ids()
        client.post(f"/expenses/{remove}/delete")
        assert _ids() == [keep]

    def test_deleted_expense_gone_from_profile(self, client, user_id, add_expense):
        add_expense(user_id, 1, "Food", "2024-01-01", "keepme")
        add_expense(user_id, 2, "Bills", "2024-01-02", "removeme")
        _, remove = _ids()
        r = client.post(f"/expenses/{remove}/delete", follow_redirects=True)
        assert r.status_code == 200
        assert b"removeme" not in r.data
        assert b"keepme" in r.data

    def test_stats_recalculated_after_delete(self, client, user_id, add_expense):
        add_expense(user_id, 111.0, "Food", "2024-01-01", "big")
        add_expense(user_id, 7.0, "Bills", "2024-01-02", "small")
        big = _ids()[0]
        r = client.post(f"/expenses/{big}/delete", follow_redirects=True)
        assert b"111.00" not in r.data, "Deleted amount should not be in totals"
        assert b"7.00" in r.data

    def test_second_post_404(self, client, expense_id):
        assert client.post(f"/expenses/{expense_id}/delete").status_code == 302
        assert client.post(f"/expenses/{expense_id}/delete").status_code == 404

    def test_get_after_delete_404(self, client, expense_id):
        client.post(f"/expenses/{expense_id}/delete")
        assert client.get(f"/expenses/{expense_id}/delete").status_code == 404

    def test_deleting_only_expense_shows_empty_state(self, client, expense_id):
        r = client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)
        assert r.status_code == 200
        assert b"No transactions yet" in r.data


class TestProfileLinks:
    def test_profile_rows_have_delete_link(self, client, user_id, add_expense):
        add_expense(user_id, 1, "Food", "2024-01-01", "one")
        add_expense(user_id, 2, "Bills", "2024-01-02", "two")
        body = client.get("/profile").data.decode()
        for eid in _ids():
            assert f'href="/expenses/{eid}/delete"' in body, f"Missing Delete link for {eid}"

    def test_profile_delete_link_opens_confirmation(self, client, expense_id):
        body = client.get("/profile").data.decode()
        assert f'href="/expenses/{expense_id}/delete"' in body
        r = client.get(f"/expenses/{expense_id}/delete")
        assert r.status_code == 200
        assert b"Lunch special" in r.data


class TestInjection:
    def test_sql_injection_in_path_does_not_delete(self, client, expense_id):
        r = client.post("/expenses/1 OR 1=1/delete")
        assert r.status_code == 404
        assert expense_id in _ids()

    def test_non_integer_id_404(self, client, user_id):
        assert client.get("/expenses/abc/delete").status_code == 404
