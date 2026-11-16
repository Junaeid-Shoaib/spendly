# Spec: Edit Expense

## Overview
Replaces the `GET /expenses/<id>/edit` stub with a working form that lets a logged-in user change the amount, category, date and description of one of their own existing expenses. Step 7 made expenses user-generated; this step lets users correct mistakes. It reuses the add-expense validation so both forms enforce identical rules. The "Recent transactions" table on the profile page gains an Edit link per row. Delete remains a stub until Step 9.

## Depends on
- Step 01 — Database setup (`expenses` table, `get_db()`, `CATEGORIES`)
- Step 03 — Login/logout (session, `g.user`)
- Step 05 — Profile backend (recent transactions table)
- Step 07 — Add expense (`_validate_expense()`, `add_expense.css`, form layout)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form prefilled with the expense's current values — logged-in (redirect to `login` if not); `abort(404)` if the expense does not exist or belongs to another user
- `POST /expenses/<int:id>/edit` — validate and update the expense, redirect to `profile` on success; re-render the form with an error and the submitted values (HTTP 400) on failure — logged-in; `abort(404)` if missing or not owned

## Database changes
No schema changes. The existing `expenses` table is sufficient.

New helpers in `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — parameterised SELECT filtered by both `id` and `user_id`; returns a dict (`id`, `amount` float, `category`, `date`, `description`) or `None` if not found or not owned.
- `update_expense(expense_id, user_id, amount, category, expense_date, description)` — parameterised UPDATE with `WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was updated (`rowcount == 1`), else `False`; blank description stored as `NULL`.
- Extend `get_recent_expenses()` to also return `id` for each expense (needed to build edit links). Existing keys and behaviour stay unchanged.

## Templates
- **Create:** `templates/edit_expense.html` — same fields as the add form (amount, category `<select>` from `CATEGORIES`, date, description), prefilled; error area; "Save changes" button; Cancel link to `profile`. Form `action` uses `url_for('edit_expense', id=expense_id)`. Extends `base.html`; reuses `css/add_expense.css`.
- **Modify:**
  - `templates/profile.html` — add an "Actions" column to the transactions table with an Edit link per row using `url_for('edit_expense', id=tx.id)`.

## Files to change
- `app.py` — implement `edit_expense` (GET/POST), include `id` in `_build_transactions()`, import the new helpers
- `database/db.py` — add `get_expense_by_id()`, `update_expense()`; add `id` to `get_recent_expenses()` output
- `templates/profile.html` — Edit link column
- `static/css/profile.css` — small style for the Edit link / actions column (CSS variables only)
- `CLAUDE.md` — mark `/expenses/<id>/edit` implemented; list the new helpers; update the "no update/delete helpers" note to "no delete helper until Step 9"

## Files to create
- `templates/edit_expense.html`
- `tests/test_08-edit-expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic only in `database/db.py`; the route fetches, validates (via the existing `_validate_expense()`), calls the helper, and redirects
- Use `url_for()` for every link and redirect; never hardcode URLs
- Use `abort(404)` for missing or non-owned expenses — do not reveal whether an id exists for another user, and never return raw error strings
- Ownership is enforced in SQL (`AND user_id = ?`) with `user_id` taken from `g.user["id"]`, never from the form
- Reuse `_validate_expense()`; do not duplicate validation rules
- Do not implement `/expenses/<id>/delete` — it stays a stub
- Page-specific styles go in CSS files, not inline `<style>` tags
- Vanilla JS only; the form must work without JS

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` logged out redirects to `/login`
- [ ] Visiting the edit page for your own expense shows the form prefilled with its current amount, category, date and description
- [ ] Visiting the edit page for another user's expense, or a non-existent id, returns 404
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in Recent Transactions, with stats and category breakdown recalculated
- [ ] Clearing the description saves successfully and shows "—" on the profile
- [ ] Amount empty, `0`, negative, non-numeric, `nan`, or with 3+ decimal places shows an error (HTTP 400) and keeps the entered values
- [ ] An invalid category (tampered POST), an invalid date, or a future date is rejected with an error
- [ ] A description over 200 characters is rejected
- [ ] A POST to another user's expense id returns 404 and does not modify that expense
- [ ] A POST with a `user_id` form field does not change the expense's owner
- [ ] Each row in Recent Transactions has an Edit link built with `url_for` that opens the correct expense
- [ ] Cancel returns to `/profile` without saving
- [ ] Styling uses CSS variables, matches the existing black/gold theme, and works at mobile width
- [ ] `/expenses/<id>/delete` remains an unchanged stub
- [ ] `pytest` passes
