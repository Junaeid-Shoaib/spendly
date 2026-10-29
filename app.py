import os
import sqlite3
from datetime import datetime

from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (  # noqa: F401
    create_user,
    get_category_totals,
    get_db,
    get_expense_stats,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

with app.app_context():
    init_db()
    seed_db()

MIN_PASSWORD_LENGTH = 8


@app.before_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_user_by_id(user_id)
        if g.user is None:
            session.clear()


def _validate_registration(name, email, password, confirm_password):
    if not name or not email or not password:
        return "All fields are required."

    local, _, domain = email.partition("@")
    if (
        email.count("@") != 1
        or not local
        or not domain
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or any(ch.isspace() for ch in email)
    ):
        return "Please enter a valid email address."

    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if password != confirm_password:
        return "Passwords do not match."

    return None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    error = _validate_registration(name, email, password, confirm_password)
    if error is None and get_user_by_email(email):
        error = "An account with that email already exists."

    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with that email already exists."

    if error is not None:
        return render_template(
            "register.html", error=error, name=name, email=email
        ), 400

    return redirect(url_for("login", registered=1))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("landing"))

    if request.method == "GET":
        success = None
        if request.args.get("registered") == "1":
            success = "Account created. Please sign in."
        return render_template("login.html", success=success)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html", error="Email and password are required.", email=email
        ), 400

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        ), 401

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _format_member_since(created_at):
    try:
        return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")
    except (TypeError, ValueError):
        return created_at or "—"


def _format_currency(amount):
    return f"£{amount:,.2f}"


def _build_transactions(user_id):
    """Return [{"date", "description", "category", "amount"}] for the template.

    Dates stay as stored (YYYY-MM-DD), amount is a formatted string, and a
    missing description is shown as an em dash.
    """
    return [
        {
            "date": expense["date"],
            "description": (expense["description"] or "").strip() or "—",
            "category": expense["category"],
            "amount": _format_currency(expense["amount"]),
        }
        for expense in get_recent_expenses(user_id)
    ]


def _build_stats(user_id):
    """Return {"total_spent": str, "transaction_count": int, "top_category": str}."""
    stats = get_expense_stats(user_id)
    return {
        "total_spent": _format_currency(stats["total"]),
        "transaction_count": stats["count"],
        "top_category": stats["top_category"] or "—",
    }


def _build_categories(user_id):
    """Return [{"name", "total": str, "percent": int, "bar": int}] for the template.

    percent is the true share and sums to 100; bar is percent rounded to the
    nearest 5, matching the bar-w-N classes in profile.css.
    """
    totals = get_category_totals(user_id)
    grand_total = sum(item["total"] for item in totals)
    if grand_total <= 0:
        return []

    # Largest-remainder method so the percents add up to exactly 100.
    shares = [item["total"] / grand_total * 100 for item in totals]
    percents = [int(share) for share in shares]
    leftover = 100 - sum(percents)
    by_remainder = sorted(
        range(len(shares)), key=lambda i: (-(shares[i] - percents[i]), i)
    )
    for index in by_remainder[:leftover]:
        percents[index] += 1

    categories = []
    for item, percent in zip(totals, percents):
        bar = min(100, int(percent / 5 + 0.5) * 5)
        if percent > 0:
            bar = max(bar, 5)
        categories.append(
            {
                "name": item["name"],
                "total": _format_currency(item["total"]),
                "percent": percent,
                "bar": bar,
            }
        )
    return categories


@app.route("/profile")
def profile():
    if g.user is None:
        return redirect(url_for("login"))
    user_id = g.user["id"]
    return render_template(
        "profile.html",
        user=g.user,
        member_since=_format_member_since(g.user["created_at"]),
        stats=_build_stats(user_id),
        transactions=_build_transactions(user_id),
        categories=_build_categories(user_id),
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
