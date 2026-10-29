# Spec: Profile Backend Routes

## Overview
Replace the static sample data on `/profile` (`SAMPLE_STATS`, `SAMPLE_TRANSACTIONS`, `SAMPLE_CATEGORIES` in `app.py`) with real figures computed from the logged-in user's rows in the `expenses` table. This is Step 5 of the Spendly roadmap: Step 4 shipped the profile page design with placeholder data, and this step wires the stats row, the recent-transactions table and the spending-by-category breakdown to the database. All SQL lives in new helpers in `database/db.py`; the route only checks login, fetches data, formats it for display and renders `profile.html`. The template contract (`stats`, `transactions`, `categories`) stays the same, so `profile.html` needs little or no change.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`, `seed_db()`)
- Step 3 — Login and logout (`g.user`, session handling)
- Step 4 — Profile page design (`profile.html`, `profile.css`, sample-data contract)

## Routes
- `GET /profile` — render the profile page with real expense data for `g.user`; redirect to `url_for('login')` if not logged in — logged-in (modified; data source changes, behaviour for logged-out users is unchanged)

No other new routes. `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs; do not add links to them.

## Database changes
No schema changes. Verified against `database/db.py`: the `expenses` table already has `user_id`, `amount`, `category`, `date` and `description`, and `get_db()` enables `PRAGMA foreign_keys = ON`.

New query helpers to add to `database/db.py` (each takes `user_id`, uses `?` placeholders, opens and closes its own connection like the existing helpers):
- `get_expense_stats(user_id)` — returns total spent, transaction count and top category (the category with the highest total; `None` when the user has no expenses). Ties are broken alphabetically by category name so the result is deterministic.
- `get_recent_expenses(user_id, limit=5)` — most recent expenses ordered by `date DESC, id DESC`, returning date, description, category and amount.
- `get_category_totals(user_id)` — per-category totals ordered by total descending (then category name), for the breakdown.

An optional index on `expenses(user_id)` may be added via `CREATE INDEX IF NOT EXISTS` in `init_db()`; this is not required.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — only if needed: render an empty state when the user has no expenses (a short message instead of an empty table, and no category rows); keep the existing structure, classes and `url_for` usage

## Files to change
- `database/db.py` — add the three helpers above (and the optional index)
- `app.py` — remove the `SAMPLE_*` constants; in `profile()` call the helpers and build the display values (currency formatting, percent per category) via small private formatting helpers; update the module comment
- `CLAUDE.md` — update the `/profile` row in the routes table (no longer static sample data) and fix the stale notes that `database/db.py` is empty and that `/logout` is a stub
- `tests/test_profile.py` — extend (see below)

## Files to create
- `tests/test_profile_data.py` — tests for the three db helpers and for the `/profile` route using real data (uses the existing `temp_db` and `client` fixtures from `conftest.py`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings or string formatting in SQL
- Passwords hashed with werkzeug — never expose `password_hash` to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`; route functions only fetch, format and render
- Every query is scoped by `user_id = ?` so a user only ever sees their own expenses
- Currency keeps the `£` symbol used by the Step 4 design, formatted with thousands separators and two decimals (for example `£1,299.00`); do this in one formatting helper in `app.py`
- Category percentages are whole numbers computed from the category total over the grand total. `profile.css` only defines `bar-w-<n>` classes in steps of 5 (`bar-w-0` to `bar-w-100`), so round the bar class to the nearest 5 while displaying the true rounded percent; do not add inline `style=` attributes
- Dates are shown as stored (`YYYY-MM-DD`); a missing description is shown as an em dash, not `None`
- A user with no expenses must see a working page: total `£0.00`, 0 transactions, top category `—`, no errors
- Do not implement the other stub routes (`/expenses/add`, edit, delete)
- Escape all user-supplied values (Jinja2 autoescape; no `|safe`)
- Do not change the port (5001) or the `before_request` login behaviour

## Definition of done
- [ ] Logged out, `/profile` still redirects (302) to `/login`
- [ ] Logged in as `demo@spendly.com` / `demo123`, `/profile` returns 200
- [ ] Total spent for the demo user is `£5,014.74` and the transaction count is 8, matching the seeded rows
- [ ] The top category for the demo user is `Bills`
- [ ] The recent-transactions table shows at most 5 rows, newest first, with the seeded dates, descriptions, categories and amounts; the row with no description shows an em dash
- [ ] The category breakdown shows every category the user has spent in (including Transport, which the old sample data omitted), ordered by total descending, and the percents sum to roughly 100
- [ ] A newly registered user with no expenses sees `£0.00`, 0 transactions, top category `—` and an empty state, with no error
- [ ] A second user's expenses never appear on another user's profile
- [ ] No `SAMPLE_*` constants remain in `app.py`
- [ ] No SQL in the codebase uses string formatting or f-strings
- [ ] `pytest` passes, including the new `tests/test_profile_data.py`
- [ ] App starts on port 5001 without errors
