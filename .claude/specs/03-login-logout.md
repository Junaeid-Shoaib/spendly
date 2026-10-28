# Spec: Login and Logout

## Overview
Turn the existing `GET /login` page into a working sign-in flow and replace the `/logout` stub with a real session-ending route. A registered user submits email and password; the app verifies the werkzeug hash, stores the user id in the Flask session and redirects to the next page. Logout clears the session. This is Step 3 of the Spendly roadmap: it follows registration (Step 2) and is the prerequisite for every logged-in feature (profile, add/edit/delete expense).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`)
- Step 2 — Registration (`create_user()`, `get_user_by_email()`, redirect to `/login?registered=1`)

## Routes
- `GET /login` — render the sign-in form; if already logged in, redirect to `/` (landing) — public (already implemented, modified)
- `POST /login` — validate credentials, set `session["user_id"]`, redirect to `/` (landing) on success; re-render the form with an error and HTTP 400/401 on failure — public
- `GET /register` and `POST /register` — (Step 2 routes, modified) if already logged in, redirect to `/` (landing) without showing the form or creating an account
- `GET /logout` — clear the session and redirect to `/` (landing) — logged-in (harmless if called while logged out)

`/profile` is still a stub (Step 4) that returns a plain string with no navbar, so login redirects to the landing page (`url_for('landing')`) for now. Switch to `profile` when Step 4 ships.

## Database changes
No database changes. The existing `users` table already has `email` and `password_hash`.

Add one helper to `database/db.py`:
- `get_user_by_id(user_id)` — returns the matching `sqlite3.Row` or `None`, parameterised query. Used to load the current user for the navbar.

Authentication reuses `get_user_by_email()` and werkzeug's `check_password_hash`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — form `action="{{ url_for('login') }}"` (currently hardcoded `/login`); keep the submitted `email` on re-render after an error (`value="{{ email or '' }}"`); never re-populate the password.
  - `templates/base.html` — navbar shows "Sign in" / "Get started" when logged out, and the user's name plus a "Sign out" link (`url_for('logout')`) when logged in. Use `g.user` (or a context processor) — no DB logic in the template.

## Files to change
- `app.py` — set `app.secret_key`; make `/login` accept `GET` and `POST`; add the POST handler; implement `/logout`; add a `before_request` hook that loads `g.user` from the session; import `session`, `g`, `abort` as needed and the new db helper
- `database/db.py` — add `get_user_by_id()`
- `templates/login.html` — as above
- `templates/base.html` — as above
- `CLAUDE.md` — update the routes table (`/login` POST and `/logout` implemented) if the project owner wants it

## Files to create
- `tests/test_login_logout.py` — route tests for successful login, bad password, unknown email, empty fields, logout, and navbar state (use the existing `conftest.py` fixtures; check its setup before writing)

## New dependencies
No new dependencies. Flask's built-in signed-cookie `session` is used.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`; the route only reads the form, calls helpers, and renders or redirects
- Use `url_for()` for every link and redirect — no hardcoded URLs
- Secret key: read from an environment variable (e.g. `SECRET_KEY`) with a clearly-labelled development fallback; do not commit a production secret
- Use one generic error message for both unknown email and wrong password ("Invalid email or password.") to avoid account enumeration
- Normalise the email (`.strip().lower()`) before lookup, matching registration
- Call `session.clear()` before setting `user_id` on login to avoid session fixation
- Validation failure renders the template with `error` — no bare string returns; use `abort()` for HTTP errors
- Do not use an open redirect: do not honour a `next` parameter unless it is a relative path on this app (or simply omit `next` support)
- Logged-in users must not reach the login or register forms: both routes redirect to `url_for('landing')` when `g.user` is set
- Do not implement `/profile` or any other stub route
- Keep the existing `?registered=1` success banner working

## Definition of done
- [ ] `GET /login` renders the form; the `?registered=1` banner still appears
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) and sets a session cookie
- [ ] Email matching is case-insensitive (`DEMO@Spendly.com` works)
- [ ] A wrong password shows "Invalid email or password." and sets no session
- [ ] An unknown email shows the same message as a wrong password
- [ ] Empty email or password shows an error and sets no session
- [ ] After a failed login the email field keeps its value; the password field is empty
- [ ] Visiting `/login` while logged in redirects away from the form (GET and POST)
- [ ] Visiting `/register` while logged in redirects to `/` (GET and POST); a POST creates no new user
- [ ] When logged in, the navbar shows the user's name and a "Sign out" link; when logged out it shows "Sign in" and "Get started"
- [ ] `GET /logout` clears the session and redirects to `/`; the navbar returns to the logged-out state
- [ ] `GET /logout` while logged out does not error
- [ ] The login form's `action` is generated with `url_for('login')`
- [ ] No SQL in the codebase uses string formatting or f-strings
- [ ] `pytest` passes, including the new `tests/test_login_logout.py`
- [ ] App starts on port 5001 without errors
