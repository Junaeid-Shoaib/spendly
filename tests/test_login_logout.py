import pytest

VALID = {"name": "Jane Doe", "email": "jane@example.com", "password": "password123"}


def _make_user(temp_db, **overrides):
    data = {**VALID, **overrides}
    return temp_db.create_user(data["name"], data["email"], data["password"])


def _post(client, **overrides):
    data = {"email": VALID["email"], "password": VALID["password"], **overrides}
    return client.post("/login", data=data)


def _session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def test_login_form_renders_without_error(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'action="/login"' in response.data
    assert b"auth-error" not in response.data


def test_registered_banner_still_shows(client):
    response = client.get("/login?registered=1")
    assert b"Account created. Please sign in." in response.data


def test_valid_login_redirects_and_sets_session(client, temp_db):
    user_id = _make_user(temp_db)
    response = _post(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert _session_user_id(client) == user_id


@pytest.mark.parametrize("email", ["JANE@Example.com", "  jane@example.com "])
def test_email_is_case_and_whitespace_insensitive(client, temp_db, email):
    user_id = _make_user(temp_db)
    response = _post(client, email=email)
    assert response.status_code == 302
    assert _session_user_id(client) == user_id


def test_wrong_password_and_unknown_email_look_identical(client, temp_db):
    _make_user(temp_db)
    wrong_password = _post(client, password="not-the-password")
    unknown_email = _post(client, email="nobody@example.com")
    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert b"Invalid email or password." in response.data
        assert _session_user_id(client) is None


@pytest.mark.parametrize(
    "overrides", [{"email": ""}, {"password": ""}, {"email": "   "}]
)
def test_empty_fields_are_rejected(client, temp_db, overrides):
    _make_user(temp_db)
    response = _post(client, **overrides)
    assert response.status_code == 400
    assert b"auth-error" in response.data
    assert _session_user_id(client) is None


def test_failed_login_keeps_email_but_not_password(client, temp_db):
    _make_user(temp_db)
    response = _post(client, password="wrong-password-xyz")
    html = response.get_data(as_text=True)
    assert 'value="jane@example.com"' in html
    assert "wrong-password-xyz" not in html


def test_email_is_escaped_on_rerender(client):
    response = _post(client, email='"><script>alert(1)</script>')
    assert b"<script>alert(1)</script>" not in response.data


def test_login_redirects_when_already_logged_in(client, temp_db):
    _make_user(temp_db)
    _post(client)
    get_response = client.get("/login")
    post_response = _post(client)
    for response in (get_response, post_response):
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")


def test_register_redirects_when_already_logged_in(client, temp_db):
    _make_user(temp_db)
    _post(client)
    get_response = client.get("/register")
    post_response = client.post(
        "/register",
        data={**VALID, "email": "other@example.com", "confirm_password": VALID["password"]},
    )
    for response in (get_response, post_response):
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
    assert temp_db.get_user_by_email("other@example.com") is None


def test_navbar_when_logged_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_navbar_when_logged_in(client, temp_db):
    _make_user(temp_db)
    _post(client)
    html = client.get("/").get_data(as_text=True)
    assert "Jane Doe" in html
    assert 'href="/logout"' in html
    assert "Get started" not in html


def test_logout_clears_session_and_redirects(client, temp_db):
    _make_user(temp_db)
    _post(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert _session_user_id(client) is None
    assert "Sign out" not in client.get("/").get_data(as_text=True)


def test_logout_while_logged_out_does_not_error(client):
    response = client.get("/logout")
    assert response.status_code == 302


def test_stale_session_is_cleared(client, temp_db):
    user_id = _make_user(temp_db)
    _post(client)
    conn = temp_db.get_db()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    response = client.get("/")
    assert response.status_code == 200
    assert "Sign out" not in response.get_data(as_text=True)
    assert _session_user_id(client) is None


def test_login_discards_preexisting_session_data(client, temp_db):
    _make_user(temp_db)
    with client.session_transaction() as sess:
        sess["junk"] = "x"
    _post(client)
    with client.session_transaction() as sess:
        assert "junk" not in sess
