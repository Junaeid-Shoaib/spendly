# Spec: Delete Expense

## Overview
Replaces the `/expenses/<id>/delete` stub with a working delete flow that lets a logged-in user permanently remove one of their own expenses. Steps 7 and 8 let users add and correct expenses; this step completes the expense lifecycle. Because deletion is destructive, the GET route only renders a confirmation page (it never deletes); the actual deletion happens on POST, so a link prefetch, crawler or stray navigation can never remove data. The "Recent transactions" table on the profile page gains a Delete link beside Edit.

## Depends on
- Step 01 — Database setup (`expenses` table, `get_db()`)
- Step 03 — Login/logout (session, `g.user`)
- Step 05 — Profile backend (recent transactions table, `_build_transactions()` includes `id`)
- Step 07 — Add expense (`add_expense.css`, form/card layout)
- Step 08 — Edit expense (`get_expense_by_id()`, Actions column, ownership pattern)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the expense's date, category, description and amount, with "Delete" and "Cancel" actions — logged-in (redirect to `login` if not); `abort(404)` if the expense does not exist or belongs to another user. Does not modify data.
- `POST /expenses/<int:id>/delete` — delete the expense and redirect to `profile` — logged-in (redirect to `login` if not); `abort(404)` if missing or not owned

The existing route registration changes from GET-only to `methods=["GET", "POST"]`.

## Database changes
No schema changes. The existing `expenses` table is sufficient.

New helper in `database/db.py`:
- `delete_expense(expense_id, user_id)` — parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was deleted (`rowcount == 1`), else `False`.

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; reuses `css/add_expense.css` card layout. Shows a short "Delete this expense?" heading, a read-only summary of the expense (date, category, description or "—", amount formatted with `_format_currency`), a warning that this cannot be undone, a `<form method="post" action="{{ url_for('delete_expense', id=expense_id) }}">` with a "Delete expense" button, and a Cancel link to `url_for('profile')`.
- **Modify:**
  - `templates/profile.html` — add a Delete link next to the Edit link in the `tx-actions` cell, using `url_for('delete_expense', id=tx.id)`.

## Files to change
- `app.py` — implement `delete_expense` (GET/POST), import `delete_expense` helper (alias the import or name the helper `delete_expense_by_id` if the name collides with the route function — the route function name must stay `delete_expense` so `url_for('delete_expense', ...)` keeps working)
- `database/db.py` — add `delete_expense()` helper
- `templates/profile.html` — Delete link
- `static/css/profile.css` — style for the Delete link / actions cell (CSS variables only; destructive link uses an existing danger/error colour variable)
- `static/css/add_expense.css` — styles for the confirmation summary and a danger-styled submit button (CSS variables only), if not already covered
- `CLAUDE.md` — mark `/expenses/<id>/delete` implemented (GET confirm + POST delete); list the new `delete_expense` helper; remove the "no expense delete helper until Step 9" note

## Files to create
- `templates/delete_expense.html`
- `tests/test_09_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic only in `database/db.py`; the route fetches, calls the helper, and redirects
- Deletion must happen only on POST; GET must never modify data
- Use `url_for()` for every link, form action and redirect; never hardcode URLs
- Use `abort(404)` for missing or non-owned expenses — do not reveal whether an id exists for another user, and never return raw error strings
- Ownership is enforced in SQL (`AND user_id = ?`) with `user_id` taken from `g.user["id"]`, never from the form or query string
- If `delete_expense()` returns `False` on POST, `abort(404)`
- Do not add new pip packages (no Flask-WTF/CSRF library); note in the PR that CSRF tokens are out of scope for this step
- Page-specific styles go in CSS files, not inline `<style>` tags
- Vanilla JS only; the flow must work without JS (no JS `confirm()` dependency)

## Definition of done
- [ ] Visiting `/expenses/<id>/delete` logged out redirects to `/login`
- [ ] POSTing to `/expenses/<id>/delete` logged out redirects to `/login` and deletes nothing
- [ ] Visiting the delete page for your own expense shows a confirmation with its date, category, description and amount
- [ ] Visiting the delete page does not delete the expense (it still appears on `/profile` afterwards)
- [ ] Visiting the delete page for another user's expense, or a non-existent id, returns 404
- [ ] Confirming (POST) redirects to `/profile` and the expense no longer appears in Recent Transactions; stats and category breakdown are recalculated
- [ ] A POST to another user's expense id returns 404 and the expense still exists
- [ ] A POST to a non-existent id returns 404
- [ ] A second POST to the same id (already deleted) returns 404
- [ ] Deleting the user's only expense in the current filter shows the existing empty state without errors
- [ ] Each row in Recent Transactions has a Delete link built with `url_for` that opens the confirmation for the correct expense
- [ ] Cancel returns to `/profile` without deleting
- [ ] Styling uses CSS variables, matches the existing black/gold theme, the delete button is visually distinct as destructive, and works at mobile width
- [ ] `pytest` passes
