from datetime import date

import pytest


@pytest.fixture
def logged_in(client, temp_db):
    user_id = temp_db.create_user("Jane Doe", "jane@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return client


@pytest.fixture
def user_id(temp_db, logged_in):
    return temp_db.get_user_by_email("jane@example.com")["id"]


@pytest.fixture
def app_module(client):
    import app as app_module

    return app_module


def _seed(add_expense, user_id):
    add_expense(user_id, 100.0, "Food", "2026-10-01", "Lunch")
    add_expense(user_id, 50.0, "Transport", "2026-10-10", "Bus")
    add_expense(user_id, 200.0, "Bills", "2026-10-15", "Phone")
    add_expense(user_id, 25.0, "Food", "2026-10-20", "Snack")


# ---------------------------------------------------------------- db layer


def test_db_bounds_are_inclusive(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    stats = temp_db.get_expense_stats(
        user_id, start_date="2026-10-10", end_date="2026-10-15"
    )
    assert stats["count"] == 2
    assert stats["total"] == 250.0
    assert stats["top_category"] == "Bills"


def test_db_start_only_and_end_only(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    assert temp_db.get_expense_stats(user_id, start_date="2026-10-15")["count"] == 2
    assert temp_db.get_expense_stats(user_id, end_date="2026-10-01")["count"] == 1


def test_db_empty_range(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    stats = temp_db.get_expense_stats(
        user_id, start_date="2027-01-01", end_date="2027-01-31"
    )
    assert stats == {"total": 0.0, "count": 0, "top_category": None}


def test_db_category_totals_respect_range(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    totals = temp_db.get_category_totals(
        user_id, start_date="2026-10-01", end_date="2026-10-10"
    )
    assert totals == [
        {"name": "Food", "total": 100.0},
        {"name": "Transport", "total": 50.0},
    ]


def test_db_defaults_are_unfiltered(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    assert temp_db.get_expense_stats(user_id)["count"] == 4
    assert len(temp_db.get_category_totals(user_id)) == 3


def test_db_recent_respects_range_and_limit(temp_db, add_expense, user_id):
    _seed(add_expense, user_id)
    rows = temp_db.get_recent_expenses(
        user_id, start_date="2026-10-10", end_date="2026-10-20"
    )
    assert [r["date"] for r in rows] == ["2026-10-20", "2026-10-15", "2026-10-10"]
    rows = temp_db.get_recent_expenses(user_id, limit=1, start_date="2026-10-10")
    assert [r["date"] for r in rows] == ["2026-10-20"]


def test_db_range_excludes_other_users(temp_db, add_expense, user_id):
    other = temp_db.create_user("Other", "other@example.com", "password123")
    add_expense(user_id, 10.0, "Food", "2026-10-05")
    add_expense(other, 999.0, "Food", "2026-10-05")
    stats = temp_db.get_expense_stats(
        user_id, start_date="2026-10-01", end_date="2026-10-31"
    )
    assert stats["total"] == 10.0


# ------------------------------------------------------ _parse_date_filter


def test_parse_blank_is_unbounded(app_module):
    assert app_module._parse_date_filter({}) == (None, None, None)
    assert app_module._parse_date_filter({"start": " ", "end": ""}) == (
        None,
        None,
        None,
    )


def test_parse_valid_pair_and_one_sided(app_module):
    parse = app_module._parse_date_filter
    assert parse({"start": "2026-10-01", "end": "2026-10-15"}) == (
        "2026-10-01",
        "2026-10-15",
        None,
    )
    assert parse({"start": "2026-10-01"}) == ("2026-10-01", None, None)
    assert parse({"end": "2026-10-15"}) == (None, "2026-10-15", None)


@pytest.mark.parametrize(
    "args",
    [
        {"start": "abc"},
        {"end": "2026-13-45"},
        {"start": "2026-10-15", "end": "2026-10-01"},
    ],
)
def test_parse_invalid_returns_error_and_no_range(app_module, args):
    start, end, error = app_module._parse_date_filter(args)
    assert (start, end) == (None, None)
    assert error
    assert "abc" not in error and "2026" not in error  # input is not echoed


# --------------------------------------------------------- _build_presets


def test_presets_for_fixed_today(app_module):
    presets = {p["key"]: p for p in app_module._build_presets(date(2026, 10, 29))}
    assert (presets["this-month"]["start"], presets["this-month"]["end"]) == (
        "2026-10-01",
        "2026-10-29",
    )
    assert (presets["last-30-days"]["start"], presets["last-30-days"]["end"]) == (
        "2026-09-30",
        "2026-10-29",
    )
    assert (presets["all-time"]["start"], presets["all-time"]["end"]) == (None, None)


def test_presets_leap_day_and_month_boundary(app_module):
    presets = {p["key"]: p for p in app_module._build_presets(date(2028, 3, 1))}
    assert presets["last-30-days"]["start"] == "2028-02-01"
    assert presets["this-month"]["start"] == "2028-03-01"


# ------------------------------------------------------------------ route


def test_route_requires_login_with_and_without_params(client):
    for url in ("/profile", "/profile?start=2026-10-01&end=2026-10-15"):
        response = client.get(url)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


def test_route_range_filters_everything(logged_in, add_expense, user_id):
    _seed(add_expense, user_id)
    html = logged_in.get("/profile?start=2026-10-10&end=2026-10-15").get_data(
        as_text=True
    )
    assert "£250.00" in html
    assert "Phone" in html and "Bus" in html
    assert "Lunch" not in html and "Snack" not in html
    assert html.count('class="cat-row"') == 2
    assert "Showing 10 Oct 2026 – 15 Oct 2026" in html


def test_route_one_sided_filter(logged_in, add_expense, user_id):
    _seed(add_expense, user_id)
    html = logged_in.get("/profile?start=2026-10-15").get_data(as_text=True)
    assert "Phone" in html and "Snack" in html
    assert "Lunch" not in html
    assert "From 15 Oct 2026" in html


def test_route_category_percents_sum_to_100(logged_in, add_expense, user_id):
    _seed(add_expense, user_id)
    import re

    html = logged_in.get("/profile?start=2026-10-01&end=2026-10-20").get_data(
        as_text=True
    )
    percents = [int(p) for p in re.findall(r'cat-percent">(\d+)%', html)]
    assert percents and sum(percents) == 100


def test_route_empty_range(logged_in, add_expense, user_id):
    _seed(add_expense, user_id)
    html = logged_in.get("/profile?start=2027-01-01&end=2027-01-31").get_data(
        as_text=True
    )
    assert "£0.00" in html
    assert "No transactions in this period." in html
    assert "No spending in this period." in html


def test_route_no_data_at_all_keeps_original_empty_state(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "No transactions yet." in html
    assert "in this period" not in html


def test_route_no_params_matches_unfiltered(logged_in, add_expense, user_id):
    _seed(add_expense, user_id)
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "£375.00" in html
    assert "Showing" not in html
    assert "filter-error" not in html.replace(".filter-error", "")


@pytest.mark.parametrize(
    "query",
    [
        "start=abc",
        "end=2026-13-45",
        "start=2026-10-15&end=2026-10-01",
    ],
)
def test_route_invalid_input_is_unfiltered_with_error(
    logged_in, add_expense, user_id, query
):
    _seed(add_expense, user_id)
    response = logged_in.get(f"/profile?{query}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "£375.00" in html


def test_route_inputs_prefilled(logged_in):
    html = logged_in.get("/profile?start=2026-10-01&end=2026-10-15").get_data(
        as_text=True
    )
    assert 'name="start" value="2026-10-01"' in html
    assert 'name="end" value="2026-10-15"' in html


def test_route_active_preset_highlighted(logged_in, app_module):
    today = date.today()
    html = logged_in.get(
        f"/profile?start={today.replace(day=1).isoformat()}&end={today.isoformat()}"
    ).get_data(as_text=True)
    assert html.count("is-active") == 1
    assert 'aria-current="page">This month<' in html
    default_html = logged_in.get("/profile").get_data(as_text=True)
    assert default_html.count("is-active") == 1
    assert 'aria-current="page">All time<' in default_html


def test_route_last_30_days_preset_highlighted(logged_in, app_module):
    preset = next(
        p for p in app_module._build_presets() if p["key"] == "last-30-days"
    )
    html = logged_in.get(
        f"/profile?start={preset['start']}&end={preset['end']}"
    ).get_data(as_text=True)
    assert 'aria-current="page">Last 30 days<' in html


def test_route_filter_form_is_get_with_clear_link(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('method="get" action="/profile"') == 2  # months + dates
    assert 'class="btn-ghost" href="/profile">Clear<' in html


# ------------------------------------------------------- months dropdown


@pytest.mark.parametrize(
    "today, months, expected",
    [
        (date(2026, 10, 29), 1, "2026-09-29"),
        (date(2026, 10, 29), 6, "2026-04-29"),
        (date(2026, 3, 31), 1, "2026-02-28"),  # day clamped
        (date(2028, 3, 31), 1, "2028-02-29"),  # leap year
        (date(2026, 2, 15), 3, "2025-11-15"),  # crosses year boundary
    ],
)
def test_months_ago(app_module, today, months, expected):
    assert app_module._months_ago(today, months).isoformat() == expected


def test_parse_months_filter_valid(app_module):
    start, end, error, months = app_module._parse_months_filter(
        "3", today=date(2026, 10, 29)
    )
    assert (start, end, error, months) == ("2026-07-29", "2026-10-29", None, 3)


@pytest.mark.parametrize("raw", ["0", "4", "12", "abc", "-1", "2.5"])
def test_parse_months_filter_rejects_other_values(app_module, raw):
    start, end, error, months = app_module._parse_months_filter(raw)
    assert (start, end, months) == (None, None, None)
    assert error


def test_route_months_dropdown_options_and_selection(logged_in):
    html = logged_in.get("/profile?months=2").get_data(as_text=True)
    for label in ("Last 1 month<", "Last 2 months<", "Last 3 months<", "Last 6 months<"):
        assert label in html
    assert '<option value="2" selected>' in html
    assert html.count(" selected>") == 1
    assert "Showing" in html


def test_route_months_filters_by_range(logged_in, app_module, add_expense, user_id):
    today = date.today()
    add_expense(user_id, 10.0, "Food", today.isoformat(), "Recent")
    add_expense(
        user_id, 500.0, "Bills", app_module._months_ago(today, 4).isoformat(), "Old"
    )
    three = logged_in.get("/profile?months=3").get_data(as_text=True)
    assert "Recent" in three and "Old" not in three
    six = logged_in.get("/profile?months=6").get_data(as_text=True)
    assert "Recent" in six and "Old" in six


def test_route_invalid_months_is_unfiltered_with_error(
    logged_in, add_expense, user_id
):
    add_expense(user_id, 10.0, "Food", "2020-01-01", "Ancient")
    response = logged_in.get("/profile?months=99")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "Ancient" in html  # unfiltered


def test_route_no_months_means_no_option_selected(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert " selected>" not in html


def test_route_excludes_other_users(logged_in, temp_db, add_expense, user_id):
    other = temp_db.create_user("Other", "other@example.com", "password123")
    add_expense(user_id, 10.0, "Food", "2026-10-05", "Mine")
    add_expense(other, 999.0, "Food", "2026-10-05", "Theirs")
    html = logged_in.get("/profile?start=2026-10-01&end=2026-10-31").get_data(
        as_text=True
    )
    assert "Mine" in html and "Theirs" not in html
    assert "£999.00" not in html


def test_route_months_and_dates_together_is_an_error(
    logged_in, add_expense, user_id
):
    add_expense(user_id, 10.0, "Food", "2020-01-01", "Ancient")
    response = logged_in.get("/profile?months=1&start=2026-10-01")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Use either a period or a date range, not both." in html
    assert "Ancient" in html  # unfiltered
    assert " selected>" not in html


def test_footer_links_resolve_via_url_for(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert 'href="/terms"' in html and 'href="/privacy"' in html
    assert logged_in.get("/terms").status_code == 200
    assert logged_in.get("/privacy").status_code == 200


def test_logo_links_to_profile_when_logged_in(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert 'href="/profile" class="nav-brand"' in html


def test_logo_links_to_landing_when_logged_out(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/" class="nav-brand"' in html
