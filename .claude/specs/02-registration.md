# Spec: Registration

## Overview
Turn the existing `GET /register` page into a working sign-up flow. A visitor submits name, email and password; the app validates the input, stores a new user with a werkzeug-hashed password, shown a success message and redirects to the login page. This is the first write path into the `users` table created in Step 1 and is a prerequisite for login (Step 3) and every logged-in feature after it.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form — public (already implemented, unchanged)
- `POST /register` — validate form, create user, redirect to `/login` on success; re-render the form with an error on failure — public

## Database changes
No database changes. The `users` table already has `name`, `email` (UNIQUE, NOT NULL), `password_hash` and `created_at`. New helpers are added to `database/db.py`:
- `create_user(name, email, password)` — hashes the password with werkzeug, inserts the row with a parameterised query, returns the new user id. Lets `sqlite3.IntegrityError` propagate for a duplicate email.
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None` (case-insensitive lookup via `LOWER(email) = ?`, with the email lower-cased before insert and lookup).

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — change the form to `action="{{ url_for('register') }}"` (currently hardcoded `/register`); keep the `name` and `email` values on re-render after an error (`value="{{ name or '' }}"` etc.); never re-populate the password; add `minlength="8"` to the password input.

## Files to change
- `app.py` — change `/register` to accept `GET` and `POST`; add the POST handler; import `request`, `redirect`, `url_for`, `abort` as needed and the new db helpers
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — as described above
- `CLAUDE.md` — only if the project owner wants the routes table updated for `POST /register`

## Files to create
- `tests/test_registration.py` — route and db-helper tests (uses the existing `conftest.py` fixtures; check its setup before writing)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`; the route only reads the form, calls helpers, and renders or redirects
- Use `url_for()` for every link and redirect — no hardcoded URLs
- Server-side validation (do not rely on HTML `required`):
  - name, email and password are all present after `.strip()` (password is not stripped)
  - email contains a single `@` with text on both sides and a `.` in the domain
  - password is at least 8 characters
  - email is not already registered — check via `get_user_by_email()` and also catch `sqlite3.IntegrityError` to cover races
- On validation failure return the template with an `error` message and HTTP 200 (or 400); do not use bare string returns
- Do not implement `/login` POST, sessions or `/logout` — those belong to Step 3. Do not auto-login after registering.
- Do not implement any other stub routes

## Definition of done
- [ ] `GET /register` still renders the form with no errors
- [ ] Submitting valid name, email and password creates a row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is a werkzeug hash, not the plaintext password
- [ ] Submitting an email that already exists (including `demo@spendly.com` or a different letter case) shows an error and creates no new row
- [ ] Submitting with any field empty or whitespace-only shows an error and creates no row
- [ ] Submitting a password shorter than 8 characters shows an error and creates no row
- [ ] Submitting a malformed email (e.g. `abc`, `a@b`) shows an error and creates no row
- [ ] After a failed submit the name and email fields keep what the user typed; the password field is empty
- [ ] The form's `action` is generated with `url_for('register')`
- [ ] No SQL in the codebase uses string formatting or f-strings
- [ ] `pytest` passes, including the new `tests/test_registration.py`
- [ ] App starts on port 5001 without errors
