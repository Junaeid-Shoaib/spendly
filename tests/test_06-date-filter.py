"""Spec-driven tests for .claude/specs/06-date-filter.md (GET /profile?start=&end=)."""
import re
import sqlite3

import pytest

ERROR_MARK = b"filter-error"
EMPTY_PERIOD = b"No transactions in this period."
EMPTY_ALL = b"No transactions yet."


def _register_and_login(client, email, name="Tester"):
    client.post(
        "/register",
        data={"name": name, "email": email, "password": "secret123",
              "confirm_password": "secret123"},
    )
    client.post("/login", data={"email": email, "password": "secret123"})


def _user_id(temp_db, email):
    conn = temp_db.get_db()
    try:
        return conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
    finally:
        conn.close()


@pytest.fixture
def user(client, temp_db):
    _register_and_login(client, "a@example.com")
    return _user_id(temp_db, "a@example.com")


@pytest.fixture
def seeded(user, add_expense):
    """Expenses with unique amounts/descriptions across dates."""
    add_expense(user, 11.11, "Food", "2026-09-30", "SEPT-OUT")
    add_expense(user, 22.22, "Food", "2026-10-01", "OCT01-EDGE")
    add_expense(user, 33.33, "Transport", "2026-10-10", "OCT10-MID")
    add_expense(user, 44.44, "Bills", "2026-10-15", "OCT15-EDGE")
    add_expense(user, 55.55, "Shopping", "2026-10-20", "OCT20-LATE")
    return user


def _get(client, query=""):
    return client.get("/profile" + query)


class TestAuthGuard:
    @pytest.mark.parametrize("query", [
        "", "?start=2026-10-01&end=2026-10-15", "?start=abc", "?end=2026-10-15",
    ])
    def test_profile_unauthenticated_redirects_to_login(self, client, query):
        resp = _get(client, query)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestNoParams:
    def test_no_params_shows_all_expenses(self, client, seeded):
        resp = _get(client)
        assert resp.status_code == 200
        for marker in (b"SEPT-OUT", b"OCT01-EDGE", b"OCT10-MID", b"OCT15-EDGE", b"OCT20-LATE"):
            assert marker in resp.data, f"{marker!r} missing from unfiltered page"
        assert ERROR_MARK not in resp.data

    def test_blank_params_treated_as_unbounded(self, client, seeded):
        resp = _get(client, "?start=&end=")
        assert resp.status_code == 200
        assert b"SEPT-OUT" in resp.data and b"OCT20-LATE" in resp.data
        assert ERROR_MARK not in resp.data

    def test_no_expenses_shows_no_transactions_yet(self, client, user):
        resp = _get(client)
        assert resp.status_code == 200
        assert EMPTY_ALL in resp.data
        assert EMPTY_PERIOD not in resp.data


class TestRangeFiltering:
    def test_range_includes_both_endpoints_and_excludes_outside(self, client, seeded):
        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        assert resp.status_code == 200
        for marker in (b"OCT01-EDGE", b"OCT10-MID", b"OCT15-EDGE"):
            assert marker in resp.data, f"{marker!r} should be in range"
        for marker in (b"SEPT-OUT", b"OCT20-LATE"):
            assert marker not in resp.data, f"{marker!r} should be excluded"
        assert ERROR_MARK not in resp.data

    def test_stats_reflect_filtered_range(self, client, seeded):
        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        # total = 22.22 + 33.33 + 44.44 = 99.99
        assert "£99.99".encode() in resp.data, "filtered total should be £99.99"
        # unfiltered total 166.65 must not appear
        assert "£166.65".encode() not in resp.data

    def test_category_breakdown_reflects_filtered_range(self, client, seeded):
        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        assert b"Bills" in resp.data
        assert b"Shopping" not in resp.data, "out-of-range category must not appear"

    def test_only_start_filters_lower_bound(self, client, seeded):
        resp = _get(client, "?start=2026-10-10")
        assert b"OCT10-MID" in resp.data and b"OCT20-LATE" in resp.data
        assert b"SEPT-OUT" not in resp.data and b"OCT01-EDGE" not in resp.data

    def test_only_end_filters_upper_bound(self, client, seeded):
        resp = _get(client, "?end=2026-10-01")
        assert b"SEPT-OUT" in resp.data and b"OCT01-EDGE" in resp.data
        assert b"OCT10-MID" not in resp.data and b"OCT20-LATE" not in resp.data

    def test_single_day_range(self, client, seeded):
        resp = _get(client, "?start=2026-10-10&end=2026-10-10")
        assert b"OCT10-MID" in resp.data
        assert b"OCT01-EDGE" not in resp.data and b"OCT15-EDGE" not in resp.data

    def test_category_percentages_sum_to_100(self, client, seeded):
        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        pcts = [int(p) for p in re.findall(r'cat-percent">(\d+)%', resp.get_data(as_text=True))]
        assert pcts, "expected category percentages in the page"
        assert sum(pcts) == 100, f"percentages {pcts} should sum to 100"

    def test_date_inputs_prefilled_with_active_range(self, client, seeded):
        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        html = resp.get_data(as_text=True)
        assert 'type="date"' in html
        assert 'value="2026-10-01"' in html
        assert 'value="2026-10-15"' in html

    def test_filter_form_uses_get(self, client, seeded):
        html = _get(client).get_data(as_text=True)
        assert 'type="date"' in html
        assert 'name="start"' in html and 'name="end"' in html
        assert 'method="post"' not in html.lower()


class TestEmptyRange:
    def test_range_without_expenses_shows_zeroed_stats_and_empty_state(self, client, seeded):
        resp = _get(client, "?start=2025-01-01&end=2025-01-31")
        assert resp.status_code == 200
        assert "£0.00".encode() in resp.data
        assert "—".encode() in resp.data, "top category should show an em dash"
        assert EMPTY_PERIOD in resp.data
        assert EMPTY_ALL not in resp.data
        assert ERROR_MARK not in resp.data


class TestInvalidInput:
    @pytest.mark.parametrize("query", [
        "?start=abc",
        "?end=2026-13-45",
        "?start=2026-10-15&end=2026-10-01",
        "?start=2026/10/01",
        "?start=2026-10-01&end=notadate",
        "?start=2026-02-30",
    ])
    def test_invalid_input_renders_unfiltered_with_error(self, client, seeded, query):
        resp = _get(client, query)
        assert resp.status_code == 200, "invalid dates must not 500"
        assert ERROR_MARK in resp.data, "expected inline error message"
        for marker in (b"SEPT-OUT", b"OCT01-EDGE", b"OCT20-LATE"):
            assert marker in resp.data, "invalid range must leave page unfiltered"

    def test_sql_injection_in_params_is_safe(self, client, seeded):
        resp = _get(client, "?start=2026-10-01'%20OR%20'1'='1&end=x';DROP%20TABLE%20expenses;--")
        assert resp.status_code == 200
        assert ERROR_MARK in resp.data
        # table still intact
        assert b"OCT10-MID" in _get(client).data

    def test_very_long_param_does_not_500(self, client, seeded):
        resp = _get(client, "?start=" + "9" * 5000)
        assert resp.status_code == 200
        assert ERROR_MARK in resp.data


class TestPresets:
    def test_preset_links_present(self, client, seeded):
        html = _get(client).get_data(as_text=True)
        for label in ("This month", "Last 30 days", "All time"):
            assert label in html, f"preset {label!r} missing"

    def test_this_month_preset_link_targets_profile_with_start_and_end(self, client, seeded):
        html = _get(client).get_data(as_text=True)
        assert re.search(r'href="/profile\?[^"]*start=\d{4}-\d{2}-01', html), \
            "This month preset should link to /profile with start on the 1st"

    def test_last_30_days_link_spans_29_or_30_day_window(self, client, seeded):
        from datetime import date, timedelta
        html = _get(client).get_data(as_text=True)
        today = date.today()
        candidates = {(today - timedelta(days=d)).isoformat() for d in (29, 30)}
        assert any(f"start={c}" in html for c in candidates), \
            "Last 30 days preset should start 29/30 days before today"

    def test_clear_returns_to_plain_profile(self, client, seeded):
        html = _get(client, "?start=2026-10-01&end=2026-10-15").get_data(as_text=True)
        assert re.search(r'href="/profile"', html), "expected a Clear link to /profile"


class TestUserIsolation:
    def test_other_users_expenses_never_appear_in_filtered_results(
        self, client, temp_db, seeded, add_expense
    ):
        client.get("/logout")
        _register_and_login(client, "b@example.com", name="Other")
        other = _user_id(temp_db, "b@example.com")
        add_expense(other, 77.77, "Health", "2026-10-05", "OTHER-USER-ITEM")
        add_expense(seeded, 88.88, "Health", "2026-10-06", "A-SECRET-ITEM")

        resp = _get(client, "?start=2026-10-01&end=2026-10-15")
        assert b"OTHER-USER-ITEM" in resp.data
        assert b"A-SECRET-ITEM" not in resp.data
        assert b"OCT10-MID" not in resp.data
        assert "£77.77".encode() in resp.data

    def test_user_with_no_expenses_sees_empty_state_despite_others_data(
        self, client, temp_db, seeded
    ):
        client.get("/logout")
        _register_and_login(client, "c@example.com", name="Empty")
        resp = _get(client, "?start=2026-10-01&end=2026-10-31")
        assert EMPTY_PERIOD in resp.data
        assert b"OCT10-MID" not in resp.data


class TestReadOnly:
    def test_filtering_does_not_modify_expenses(self, client, temp_db, seeded):
        def snapshot():
            conn = temp_db.get_db()
            try:
                return [tuple(r) for r in conn.execute(
                    "SELECT user_id, amount, category, date, description "
                    "FROM expenses ORDER BY id").fetchall()]
            finally:
                conn.close()

        before = snapshot()
        _get(client, "?start=2026-10-01&end=2026-10-15")
        _get(client, "?start=bad")
        assert snapshot() == before, "GET filtering must not change expense rows"
        assert len(before) == 5


class TestDbHelpers:
    def test_helpers_accept_date_kwargs_and_filter_inclusively(self, temp_db, client, seeded):
        uid = seeded
        stats = temp_db.get_expense_stats(uid, start_date="2026-10-01", end_date="2026-10-15")
        assert stats is not None
        recent = temp_db.get_recent_expenses(uid, start_date="2026-10-01", end_date="2026-10-15")
        assert len(recent) == 3
        cats = temp_db.get_category_totals(uid, start_date="2026-10-01", end_date="2026-10-15")
        assert len(cats) == 3

    def test_helpers_defaults_preserve_unfiltered_behaviour(self, temp_db, client, seeded):
        recent = temp_db.get_recent_expenses(seeded, limit=10)
        assert len(recent) == 5
        assert len(temp_db.get_category_totals(seeded)) == 4

    def test_helpers_one_sided_bounds(self, temp_db, client, seeded):
        assert len(temp_db.get_recent_expenses(seeded, limit=10, start_date="2026-10-10")) == 3
        assert len(temp_db.get_recent_expenses(seeded, limit=10, end_date="2026-10-01")) == 2
