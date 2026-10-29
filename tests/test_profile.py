import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def logged_in(client, temp_db):
    user_id = temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return client


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_redirects_for_stale_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_renders_when_logged_in(logged_in):
    response = logged_in.get("/profile")
    assert response.status_code == 200
    assert b"Jane Doe" in response.data
    assert b"jane@example.com" in response.data
    assert b"Member since" in response.data
    assert b"Total spent" in response.data
    assert b"Transactions" in response.data
    assert b"Top category" in response.data


def test_profile_has_table_rows_and_categories(logged_in, temp_db, add_expense):
    user_id = temp_db.get_user_by_email("jane@example.com")["id"]
    add_expense(user_id, 100.0, "Food", "2026-10-01", "Lunch")
    add_expense(user_id, 50.0, "Transport", "2026-10-02", "Bus")
    add_expense(user_id, 200.0, "Bills", "2026-10-03", "Phone")
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count("<tr>") >= 4  # header + at least 3 rows
    assert html.count('class="cat-row"') >= 3


def test_profile_shows_real_stats(logged_in, temp_db, add_expense):
    user_id = temp_db.get_user_by_email("jane@example.com")["id"]
    add_expense(user_id, 1200.0, "Bills", "2026-10-03", "Rent")
    add_expense(user_id, 34.5, "Food", "2026-10-04", None)
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "£1,234.50" in html
    assert "bar-w-100" not in html  # Bills is ~97%, Food ~3%
    assert "bar-w-95" in html
    assert "<td>—</td>" in html  # missing description


def test_profile_empty_state_for_new_user(logged_in):
    response = logged_in.get("/profile")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "£0.00" in html
    assert "No transactions yet." in html
    assert "No spending to break down yet." in html
    assert 'class="cat-row"' not in html
    assert "<tr>" not in html


def test_profile_hides_other_users_expenses(logged_in, temp_db, add_expense):
    other_id = temp_db.create_user("Other", "other@example.com", "password123")
    add_expense(other_id, 999.0, "Shopping", "2026-10-05", "Secret purchase")
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "Secret purchase" not in html
    assert "£999.00" not in html


def test_profile_navbar_shows_logged_in_state(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "Jane Doe" in html
    assert "/logout" in html
    assert "/profile" in html


@pytest.mark.parametrize("path", ["templates/profile.html", "static/css/profile.css"])
def test_profile_files_have_no_hex_or_inline_styles(path):
    text = (ROOT / path).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text)
    assert "style=" not in text


def test_profile_does_not_expose_password_hash(logged_in):
    assert b"password_hash" not in logged_in.get("/profile").data
    assert b"pbkdf2" not in logged_in.get("/profile").data
    assert b"scrypt" not in logged_in.get("/profile").data


def test_profile_escapes_user_name(client, temp_db):
    user_id = temp_db.create_user("<script>x</script>", "xss@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    html = client.get("/profile").get_data(as_text=True)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_profile_links_stylesheet(logged_in):
    assert b"/static/css/profile.css" in logged_in.get("/profile").data


def test_login_redirects_to_profile(client, temp_db):
    temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    response = client.post(
        "/login", data={"email": "jane@example.com", "password": "password123"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
