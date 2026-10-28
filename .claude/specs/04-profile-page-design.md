# Spec: Profile Page Design

## Overview
Replace the `/profile` stub (currently a plain string, "Profile page — coming in Step 4") with a designed profile page that extends `base.html`. The page shows the logged-in user's account details (name, email, member-since date) plus a summary-stats row (total spent, transaction count, top category), a recent-transactions table and a spending-by-category breakdown. This step is design-focused: the user card is built from the real logged-in user (`g.user`), while the stats, transactions and categories use static sample data until Step 5 wires them to the `expenses` table. It follows login/logout (Step 3), which made `g.user` available, and the login redirect can switch from the landing page to the profile once this ships.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables)
- Step 2 — Registration
- Step 3 — Login and logout (`g.user` loaded by `before_request`, navbar logged-in state)

## Routes
- `GET /profile` — render the profile page; redirect to `url_for('login')` if not logged in — logged-in (modified; was a stub)

No other new routes. `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs; any links to them on the page must not be added until their steps.

## Database changes
No database changes. The existing `users` table already has `name`, `email` and `created_at`. Verified against `database/db.py`: `get_user_by_id()` already exists and is used by the `before_request` hook.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections: profile card (avatar initial, name, email, "Member since"), stats row ("Total spent", "Transactions", "Top category"), transactions table, category breakdown (`class="cat-row"` per category)
- **Modify:**
  - `templates/base.html` — add `{% block head %}` usage is already supported; change the navbar user name into a link to `url_for('profile')` when logged in
  - Link the page-specific stylesheet from `profile.html` via the `head` block (`url_for('static', filename='css/profile.css')`)

## Files to change
- `app.py` — implement `/profile` (redirect to login when `g.user is None`, otherwise render `profile.html` with the user and sample data); optionally redirect to `profile` after login
- `templates/base.html` — navbar name links to the profile
- `CLAUDE.md` — update the routes table for `/profile`

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles (no inline `<style>` tags, no `style=` attributes)
- `tests/test_profile.py` — redirect when logged out, redirect for a stale session, renders when logged in, table rows and category rows present, navbar state, no hex colours or inline styles in the new template/CSS (use the existing `conftest.py` fixtures `client` and `temp_db`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — never expose `password_hash` to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Page-specific styles live in `static/css/profile.css`, linked from the `head` block; no inline `<style>` or `style=` attributes
- Use `url_for()` for every link and redirect — no hardcoded URLs
- Route function does one thing: check login, fetch data, render. Any DB logic belongs in `database/db.py`
- Static sample data for stats/transactions/categories is clearly marked as such in `app.py` and replaced in Step 5; do not query `expenses` in this step
- Do not implement other stub routes (`/expenses/add`, edit, delete)
- Layout must be responsive (usable at mobile width) and match the existing look (fonts and variables from `style.css`)
- Escape all user-supplied values (Jinja2 autoescape; no `|safe`)

## Definition of done
- [ ] Visiting `/profile` while logged out redirects (302) to `/login`
- [ ] A session with a non-existent user id also redirects to `/login`
- [ ] Logged in as `demo@spendly.com` / `demo123`, `/profile` returns 200 and shows the user's name, email and "Member since"
- [ ] The page shows "Total spent", "Transactions" and "Top category" stat cards
- [ ] The transactions table renders a header plus at least 3 rows
- [ ] The category breakdown renders at least 3 `cat-row` entries
- [ ] The navbar shows the user's name linking to `/profile` and a "Sign out" link
- [ ] `profile.html` extends `base.html` and links `profile.css` through `url_for`
- [ ] `profile.html` and `profile.css` contain no hex colour values and no inline styles
- [ ] The layout is readable at mobile width (no horizontal scroll)
- [ ] No SQL in the codebase uses string formatting or f-strings
- [ ] App starts on port 5001 without errors
