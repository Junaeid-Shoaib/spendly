# Spec: Date Filter for Profile Page

## Overview
Adds a date-range filter to the profile page so a logged-in user can narrow the stats, recent transactions and category breakdown to a chosen period. The filter is driven by `start` and `end` query-string parameters (ISO `YYYY-MM-DD`) on `GET /profile`, with a few quick presets (This month, Last 30 days, All time) and a custom from/to form. With no parameters the page behaves exactly as it does today (all time). This builds on the real-data profile page from Step 5 and requires no new tables.

## Depends on
- Step 01 — Database setup
- Step 03 — Login / logout (session, `g.user`)
- Step 04 — Profile page design
- Step 05 — Profile backend routes (stats, recent transactions, category totals)

## Routes
No new routes.

`GET /profile` is modified to accept optional query params — logged-in only (unchanged):
- `start` — inclusive lower bound, `YYYY-MM-DD`
- `end` — inclusive upper bound, `YYYY-MM-DD`
- Missing or blank param = that side is unbounded.
- Invalid dates (bad format, or `start` > `end`) are ignored: the page renders unfiltered and shows an inline error message. It must not 500 and must not return raw error strings.

## Database changes
No database changes.

`database/db.py` helpers `get_recent_expenses()`, `get_expense_stats()` and `get_category_totals()` gain optional `start_date=None, end_date=None` keyword arguments. When provided, they add `AND date >= ?` / `AND date <= ?` to the existing `WHERE user_id = ?` clause using parameterised queries. Defaults preserve current behaviour. Dates are stored as `YYYY-MM-DD` text, so string comparison is correct.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats row: preset links (built with `url_for('profile', start=..., end=...)`), a GET form with two `<input type="date">` fields (prefilled with the active range) plus Apply and Clear controls.
  - Show an inline error message when the submitted range was invalid.
  - Show the active range label near the headings (e.g. "1 Oct 2026 – 29 Oct 2026").
  - Empty states distinguish "No transactions in this period." from "No transactions yet."

## Files to change
- `app.py` — parse/validate `start`/`end` in a helper, compute preset ranges, pass filter values to the `_build_*` helpers and the template
- `database/db.py` — optional date-range arguments on the three expense query helpers
- `templates/profile.html` — filter bar, error, empty states
- `static/css/profile.css` — styles for filter bar, presets (active state), inputs, error text
- `CLAUDE.md` — note that the profile accepts date filters (routes table / db helpers line)

## Files to create
- `.claude/specs/06-date-filter.md` (this spec)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build the date clauses with f-strings of user input (appending fixed `AND date >= ?` fragments is fine)
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`; the route only parses params, calls helpers, renders
- Validate dates with `datetime.strptime(value, "%Y-%m-%d")` in `app.py`; never pass unvalidated input to SQL
- Use `url_for()` for all links, including preset links with query args
- Page-specific styles go in `profile.css`, no inline `<style>`
- Vanilla JS only; the page must work with no JS (plain GET form)
- Do not implement the stub routes (`/expenses/add`, edit, delete)
- Filtering must remain scoped to `g.user["id"]`

## Definition of done
- [ ] `/profile` with no params shows the same stats, transactions and categories as before
- [ ] `/profile?start=2026-10-01&end=2026-10-15` shows only expenses dated in that range, inclusive of both endpoints
- [ ] Stats (total, count, top category), recent transactions and category breakdown all reflect the filtered range
- [ ] Only `start` or only `end` supplied filters one-sided correctly
- [ ] Category percentages still sum to 100 for any non-empty filtered result
- [ ] A range with no expenses shows zeroed stats ("£0.00", 0, "—") and the "No transactions in this period." empty state
- [ ] Invalid input (`start=abc`, `end=2026-13-45`, or `start` after `end`) renders the page with an error message, unfiltered, status 200
- [ ] Date inputs are prefilled with the active range; Apply submits via GET; Clear returns to `/profile`
- [ ] Preset links (This month, Last 30 days, All time) apply the right ranges and the active preset is highlighted
- [ ] Another user's expenses never appear in the filtered results
- [ ] Unauthenticated access to `/profile` (with or without params) still redirects to `/login`
- [ ] Layout works at mobile width with no horizontal scroll
