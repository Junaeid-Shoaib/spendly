import os
import sqlite3
from datetime import datetime

from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (  # noqa: F401
    create_user,
    get_db,
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


# SAMPLE DATA — static placeholder, replaced by DB queries in Step 5
SAMPLE_STATS = {
    "total_spent": "£5,014.74",
    "transaction_count": 8,
    "top_category": "Bills",
}

SAMPLE_TRANSACTIONS = [
    {"date": "2026-10-25", "description": "Dinner out", "category": "Food", "amount": "£220.00"},
    {"date": "2026-10-20", "description": "Miscellaneous", "category": "Other", "amount": "£75.25"},
    {"date": "2026-10-15", "description": "New headphones", "category": "Shopping", "amount": "£1,299.00"},
    {"date": "2026-10-12", "description": "Movie night", "category": "Entertainment", "amount": "£399.99"},
    {"date": "2026-10-05", "description": "Electricity bill", "category": "Bills", "amount": "£1,800.00"},
]

SAMPLE_CATEGORIES = [
    {"name": "Bills", "total": "£1,800.00", "percent": 35},
    {"name": "Shopping", "total": "£1,299.00", "percent": 25},
    {"name": "Food", "total": "£670.00", "percent": 15},
    {"name": "Health", "total": "£650.00", "percent": 15},
    {"name": "Entertainment", "total": "£399.99", "percent": 10},
]


def _format_member_since(created_at):
    try:
        return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")
    except (TypeError, ValueError):
        return created_at or "—"


@app.route("/profile")
def profile():
    if g.user is None:
        return redirect(url_for("login"))
    return render_template(
        "profile.html",
        user=g.user,
        member_since=_format_member_since(g.user["created_at"]),
        stats=SAMPLE_STATS,
        transactions=SAMPLE_TRANSACTIONS,
        categories=SAMPLE_CATEGORIES,
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
