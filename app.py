import sqlite3

from flask import Flask, redirect, render_template, request, url_for

from database.db import (  # noqa: F401
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)

app = Flask(__name__)

with app.app_context():
    init_db()
    seed_db()

MIN_PASSWORD_LENGTH = 8


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


@app.route("/login")
def login():
    success = None
    if request.args.get("registered") == "1":
        success = "Account created. Please sign in."
    return render_template("login.html", success=success)


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
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
