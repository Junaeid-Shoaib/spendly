import sqlite3

import pytest
from werkzeug.security import check_password_hash

VALID = {"name": "Jane Doe", "email": "jane@example.com", "password": "password123"}


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _user_count(temp_db):
    conn = temp_db.get_db()
    try:
        return _count(conn, "users")
    finally:
        conn.close()


def _post(client, **overrides):
    data = {**VALID, **overrides}
    data.setdefault("confirm_password", data["password"])
    return client.post("/register", data=data)


def test_mismatched_passwords_are_rejected(client, temp_db):
    response = _post(client, confirm_password="different123")
    assert response.status_code == 400
    assert b"Passwords do not match" in response.data
    assert _user_count(temp_db) == 0


def test_missing_confirm_password_is_rejected(client, temp_db):
    response = client.post("/register", data=VALID)
    assert response.status_code == 400
    assert b"Passwords do not match" in response.data
    assert _user_count(temp_db) == 0


def test_mismatch_keeps_name_and_email_but_not_passwords(client):
    html = _post(client, confirm_password="different123").get_data(as_text=True)
    assert 'value="Jane Doe"' in html
    assert 'value="jane@example.com"' in html
    assert "password123" not in html
    assert "different123" not in html


def test_get_register_renders_form_without_error(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b'action="/register"' in response.data
    assert b"auth-error" not in response.data


def test_valid_registration_redirects_to_login(client, temp_db):
    response = _post(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login?registered=1")
    assert _user_count(temp_db) == 1


def test_valid_registration_stores_hashed_password_and_normalised_fields(
    client, temp_db
):
    _post(client, name="  Jane Doe  ", email="  Jane@Example.COM ")
    user = temp_db.get_user_by_email("jane@example.com")
    assert user["name"] == "Jane Doe"
    assert user["email"] == "jane@example.com"
    assert user["password_hash"] != VALID["password"]
    assert check_password_hash(user["password_hash"], VALID["password"])


@pytest.mark.parametrize(
    "email", ["jane@example.com", "JANE@Example.com", "demo@spendly.com"]
)
def test_duplicate_email_is_rejected(client, temp_db, email):
    temp_db.seed_db()
    temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    before = _user_count(temp_db)

    response = _post(client, email=email)

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert _user_count(temp_db) == before


@pytest.mark.parametrize("field", ["name", "email", "password"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_or_blank_field_is_rejected(client, temp_db, field, value):
    response = _post(client, **{field: value})
    assert response.status_code == 400
    assert b"auth-error" in response.data
    assert _user_count(temp_db) == 0


def test_short_password_is_rejected(client, temp_db):
    response = _post(client, password="1234567")
    assert response.status_code == 400
    assert b"at least 8" in response.data
    assert _user_count(temp_db) == 0


def test_eight_character_password_is_accepted(client, temp_db):
    response = _post(client, password="12345678")
    assert response.status_code == 302
    assert _user_count(temp_db) == 1


@pytest.mark.parametrize(
    "email",
    ["abc", "a@b", "@b.com", "a@.com", "a@b.", "a@@b.com", "a b@c.com"],
)
def test_malformed_email_is_rejected(client, temp_db, email):
    response = _post(client, email=email)
    assert response.status_code == 400
    assert b"valid email" in response.data
    assert _user_count(temp_db) == 0


def test_failed_submit_keeps_name_and_email_but_not_password(client):
    response = _post(client, password="short")
    html = response.get_data(as_text=True)
    assert 'value="Jane Doe"' in html
    assert 'value="jane@example.com"' in html
    assert "short" not in html


def test_failed_submit_escapes_user_input(client):
    response = _post(client, name='"><script>alert(1)</script>', password="x")
    html = response.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_race_on_duplicate_email_shows_error_not_500(client, temp_db, monkeypatch):
    import app as app_module

    temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    monkeypatch.setattr(app_module, "get_user_by_email", lambda email: None)

    response = _post(client)

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert _user_count(temp_db) == 1


def test_login_shows_success_message_after_registration(client):
    response = client.get("/login?registered=1")
    assert b"auth-success" in response.data
    assert b"Account created" in response.data


def test_login_without_param_shows_no_success_message(client):
    assert b"auth-success" not in client.get("/login").data
    assert b"auth-success" not in client.get("/login?registered=yes").data


def test_follow_redirect_shows_success_message(client):
    response = _post(client)
    assert response.status_code == 302
    followed = client.get(response.headers["Location"])
    assert b"Account created" in followed.data


def test_create_user_returns_id_and_rejects_duplicate(temp_db):
    user_id = temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    assert isinstance(user_id, int)
    with pytest.raises(sqlite3.IntegrityError):
        temp_db.create_user("Other", "jane@example.com", "password123")


def test_get_user_by_email_is_case_insensitive(temp_db):
    temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    assert temp_db.get_user_by_email("JANE@example.com")["name"] == "Jane Doe"
    assert temp_db.get_user_by_email("nobody@example.com") is None
