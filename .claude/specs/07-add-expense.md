# Spec: Add Expense

## Overview
Replaces the `GET /expenses/add` stub with a working form that lets a logged-in user record a new expense (amount, category, date, optional description). Until now the app only displays seeded data on the profile page; this step makes the data user-generated and is the first of the create/update/delete expense steps (7-9). On success the user is redirected to their profile, where the new expense appears in the stats, recent transactions and category breakdown.

## Depends on
- Step 01 — Database setup (`expenses` table, `get_db()`, `CATEGORIES`)
- Step 03 — Login/logout (session, `g.user`)
- Step 05 — Profile backend (profile displays expense data)

## Routes
- `GET /expenses/add` — render the add-expense form (date defaults to today) — logged-in (redirect to `login` if not)
- `POST /expenses/add` — validate and save the expense, redirect to `profile` on success; re-render the form with an error and the submitted values (HTTP 400) on failure — logged-in

## Database changes
No schema changes. The existing `expenses` table (`user_id`, `amount`, `category`, `date`, `description`) is sufficient.

New helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — parameterised INSERT, commits, returns `lastrowid`; description stored as `None` when blank.

## Templates
- **Create:** `templates/add_expense.html` — form with amount, category `<select>` (from `CATEGORIES`), date, description; error message area; Cancel link to `profile`. Extends `base.html`.
- **Modify:**
  - `templates/profile.html` — add an "Add expense" button/link using `url_for('add_expense')`.
  - `templates/base.html` — add an "Add expense" nav link for logged-in users only if it fits the existing nav (use `url_for`).

## Files to change
- `app.py` — make `add_expense` accept GET/POST, add validation helper, import `CATEGORIES` and `create_expense`
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — link to add form
- `templates/base.html` — optional nav link
- `CLAUDE.md` — mark `/expenses/add` implemented; list `create_expense()` among helpers

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles (no inline `<style>`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic only in `database/db.py`; the route fetches/validates, calls the helper, and redirects
- Use `url_for()` for every link and redirect
- Use `abort()` for HTTP errors, not raw strings; do not implement the edit/delete stubs
- Validation (server-side):
  - amount: required, parses as a number, greater than 0, at most 2 decimal places, finite (reject `nan`/`inf`)
  - category: must be one of `CATEGORIES`
  - date: required, valid `YYYY-MM-DD`; future dates are rejected
  - description: optional, stripped, max 200 characters
- `user_id` always comes from `g.user["id"]`, never from the form
- Vanilla JS only; the form must work without JS

## Definition of done
- [ ] Visiting `/expenses/add` logged out redirects to `/login`
- [ ] Visiting `/expenses/add` logged in shows the form with today's date prefilled and all 7 categories in the dropdown
- [ ] Submitting a valid expense redirects to `/profile` and the expense appears in Recent Transactions, with total spent, transaction count and category breakdown updated
- [ ] Leaving description blank saves successfully and shows "—" on the profile
- [ ] Amount empty, `0`, negative, non-numeric, `nan`, or with 3+ decimal places shows an error and keeps the other entered values
- [ ] An invalid category (tampered POST) is rejected with an error
- [ ] An invalid or future date is rejected with an error
- [ ] A description over 200 characters is rejected
- [ ] A POST with a `user_id` form field does not affect which user owns the expense
- [ ] The profile page has a working "Add expense" link built with `url_for`
- [ ] Cancel returns to `/profile` without saving
- [ ] Styling uses CSS variables and matches the existing black/gold theme; layout works on mobile width
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` remain unchanged stubs
- [ ] `pytest` passes
