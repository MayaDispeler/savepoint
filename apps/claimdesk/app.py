"""ClaimDesk 98 - a synthetic 1998-style claims screen with six planted quirks (see quirks.py)."""
import os
import sqlite3
import time
from datetime import UTC, datetime

import quirks
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

DB_PATH = os.environ.get("CLAIMDESK_DB", "claimdesk.db")
STATUSES = ["open", "review", "approved", "paid"]


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "claimdesk-synthetic-not-a-secret"

    def db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(os.environ.get("CLAIMDESK_DB", DB_PATH))
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close(_exc):
        if con := g.pop("db", None):
            con.close()

    def now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @app.before_request
    def guard():
        if request.endpoint in {"login", "healthz", "static"}:
            return None
        if "user" not in session:
            return redirect(url_for("login"))
        if quirks.enabled("session_timeout") and time.time() - session.get("last", 0) > quirks.session_timeout_s():
            session.clear()
            flash("Your session has timed out. Please log in again.")
            return redirect(url_for("login"))
        session["last"] = time.time()
        return None

    @app.context_processor
    def ctx():
        return {"q": quirks.enabled, "save_delay_ms": quirks.save_delay_ms()}

    @app.get("/healthz")
    def healthz():
        db().execute("SELECT 1")
        return {"ok": True}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            session["user"] = request.form.get("user", "adjuster") or "adjuster"
            session["last"] = time.time()
            return redirect(url_for("claims"))
        return render_template("login.html")

    @app.get("/")
    def index():
        return redirect(url_for("claims"))

    @app.get("/claims")
    def claims():
        size = quirks.grid_page_size()
        page = max(1, request.args.get("page", 1, type=int))
        total = db().execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        rows = db().execute("SELECT * FROM claims ORDER BY id LIMIT ? OFFSET ?",
                            (size, (page - 1) * size)).fetchall()
        pages = max(1, -(-total // size))
        return render_template("claims.html", rows=rows, page=page, pages=pages, total=total)

    def get_claim(cid: str):
        row = db().execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        if row is None:
            abort(404)
        return row

    @app.get("/claims/<cid>")
    def claim(cid: str):
        notes = db().execute("SELECT * FROM claim_notes WHERE claim_id=? ORDER BY id", (cid,)).fetchall()
        adjusters = db().execute("SELECT * FROM adjusters ORDER BY id").fetchall()
        return render_template("claim.html", c=get_claim(cid), notes=notes, adjusters=adjusters,
                               statuses=STATUSES)

    @app.post("/claims/<cid>/save")
    def save_claim(cid: str):
        get_claim(cid)
        try:
            amount = round(float(request.form["amount"]), 2)
            if amount < 0:
                raise ValueError
        except (KeyError, ValueError):
            flash("Error: amount must be a non-negative number.")
            return redirect(url_for("claim", cid=cid))
        status = request.form.get("status", "open")
        if status not in STATUSES:
            abort(400)
        db().execute("UPDATE claims SET amount=?, status=?, adjuster_id=?, updated_at=? WHERE id=?",
                     (amount, status, request.form["adjuster_id"], now(), cid))
        db().commit()
        flash("Saved.")
        return redirect(url_for("claim", cid=cid))

    @app.post("/claims/<cid>/notes")
    def add_note(cid: str):
        get_claim(cid)
        body = request.form.get("body", "").strip()
        if not body:
            if quirks.enabled("silent_validation"):
                flash("Saved.")  # quirk: reports success, writes nothing
            else:
                flash("Error: note cannot be empty.")
            return redirect(url_for("claim", cid=cid))
        db().execute("INSERT INTO claim_notes (claim_id, body, created_at) VALUES (?,?,?)",
                     (cid, body, now()))
        db().execute("UPDATE claims SET updated_at=? WHERE id=?", (now(), cid))
        db().commit()
        flash("Saved.")
        return redirect(url_for("claim", cid=cid))

    @app.post("/claims/<cid>/delete")
    def delete_claim(cid: str):
        get_claim(cid)
        db().execute("DELETE FROM claim_notes WHERE claim_id=?", (cid,))
        db().execute("DELETE FROM claims WHERE id=?", (cid,))
        db().commit()
        flash(f"Claim {cid} deleted.")
        return redirect(url_for("claims"))

    @app.get("/payees")
    def payees():
        rows = db().execute("SELECT * FROM payees ORDER BY id").fetchall()
        return render_template("payees.html", rows=rows)

    @app.post("/payees/<pid>")
    def update_payee(pid: str):
        db().execute("UPDATE payees SET bank_account=? WHERE id=?", (request.form["bank_account"], pid))
        db().commit()
        flash("Saved.")
        return redirect(url_for("payees"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")))
