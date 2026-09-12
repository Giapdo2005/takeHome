"""
Mock target application — a deliberately legacy-flavored credit-union admin
console. Server-rendered, table layouts, no data-testid attributes. This is the
ONE concrete surface implemented against (see REPORT.md sections 1 and 4 for how
the design generalizes past it).

Auth is fake by design: any non-empty username/password logs in. A real deployment
authenticates against a real identity provider and the automation never sees a raw
credential — see .env.example's MOCKAPP_USERNAME/PASSWORD, which the discovery
agent will read at run time (Day 4), never hardcode, and never write into an artifact.

Happy path only today (Day 2). Error injection (member not found is already here
since "not found" is core to search; session timeout, interstitials, forced
failures) is added on Day 8 once replay exists to handle them.

Run:  python -m mockapp.app        -> http://localhost:8080
"""

from __future__ import annotations

import functools

from flask import Flask, redirect, render_template, request, session, url_for

from mockapp.data import find_member, next_subaccount_number

app = Flask(__name__)
app.secret_key = "dev-only-not-a-real-secret"  # mock app, never deployed, fine as-is


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.get("/")
def index():
    return redirect(url_for("dashboard") if "user" in session else url_for("login"))


@app.get("/login")
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not password:
        return render_template("login.html", error="Username and password are required."), 400
    session["user"] = username
    return redirect(url_for("dashboard"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=session["user"])


@app.get("/reports")
@login_required
def reports():
    return render_template("stub.html", title="Reports")


@app.get("/search")
@login_required
def search():
    member_id = request.args.get("member_id", "").strip()
    searched = bool(member_id)
    member = find_member(member_id) if searched else None
    return render_template(
        "search.html", searched=searched, member_id=member_id, member=member
    )


@app.get("/members/<member_id>")
@login_required
def member_detail(member_id):
    member = find_member(member_id)
    if member is None:
        return redirect(url_for("search"))
    return render_template("member_detail.html", member_id=member_id, member=member)


@app.get("/members/<member_id>/close")
@login_required
def member_close(member_id):
    # Deliberately inert. This route exists only so "Close Account" is a real,
    # clickable, irreversible-sounding control on the detail page — the target
    # the safety allowlist's risky-control pattern is meant to catch. Nothing in
    # the demo ever calls it.
    return redirect(url_for("member_detail", member_id=member_id))


@app.get("/members/<member_id>/subaccount/new")
@login_required
def subaccount_new(member_id):
    member = find_member(member_id)
    if member is None:
        return redirect(url_for("search"))
    return render_template(
        "subaccount_new.html", member_id=member_id, member=member, error=None
    )


@app.post("/members/<member_id>/subaccount/new")
@login_required
def subaccount_create(member_id):
    member = find_member(member_id)
    if member is None:
        return redirect(url_for("search"))

    account_type = request.form.get("account_type", "")
    deposit_raw = request.form.get("initial_deposit", "")

    error = None
    deposit = None
    if account_type not in ("Savings", "Checking"):
        error = "Choose an account type."
    else:
        try:
            deposit = float(deposit_raw)
            if deposit <= 0:
                error = "Initial deposit must be greater than 0."
        except ValueError:
            error = "Initial deposit must be a number."

    if error:
        return (
            render_template(
                "subaccount_new.html", member_id=member_id, member=member, error=error
            ),
            400,
        )

    subaccount_number = next_subaccount_number()
    return render_template(
        "subaccount_review.html",
        member_id=member_id,
        member=member,
        account_type=account_type,
        initial_deposit=f"{deposit:.2f}",
        subaccount_number=subaccount_number,
    )


@app.post("/members/<member_id>/subaccount/confirm")
@login_required
def subaccount_confirm(member_id):
    # Stub — deliberately not implemented. The capability's success condition is
    # reaching the review screen (subaccount_create above); this route is the
    # terminal irreversible action the safety policy blocks. Never called in the demo.
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
