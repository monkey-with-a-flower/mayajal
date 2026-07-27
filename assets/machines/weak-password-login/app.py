from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Flask, redirect, render_template_string, request, session


app = Flask(__name__)
app.secret_key = "mayajal-demo-secret"
logging.basicConfig(level=logging.INFO, format="%(message)s")

USERS = {
    "admin": "password123",
    "hr.manager": "welcome1",
}

LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Northstar Payroll Login</title>
    <style>
      body { font-family: Arial, sans-serif; background: #f3f7f4; color: #17231f; margin: 0; }
      main { max-width: 420px; margin: 10vh auto; background: white; border: 1px solid #d8e4dc; border-radius: 8px; padding: 28px; }
      h1 { margin-top: 0; font-size: 24px; }
      label { display: block; margin-top: 16px; font-weight: 700; }
      input { width: 100%; box-sizing: border-box; min-height: 42px; margin-top: 6px; border: 1px solid #b9c8bf; border-radius: 6px; padding: 0 10px; }
      button { margin-top: 20px; min-height: 42px; width: 100%; border: 0; border-radius: 6px; background: #2f6f5f; color: white; font-weight: 800; }
      .error { margin-top: 16px; background: #fdecea; color: #9d261d; padding: 10px; border-radius: 6px; font-weight: 700; }
    </style>
  </head>
  <body>
    <main>
      <h1>Northstar Payroll</h1>
      <p>Employee payroll portal</p>
      {% if error %}<div class="error">{{ error }}</div>{% endif %}
      <form method="post" action="/login">
        <label>Username<input name="username" autocomplete="username"></label>
        <label>Password<input name="password" type="password" autocomplete="current-password"></label>
        <button type="submit">Sign in</button>
      </form>
    </main>
  </body>
</html>
"""


def client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def log_login_event(outcome: str, username: str) -> None:
    app.logger.info(
        "mayajal_weak_password_login outcome=%s username=%s source_ip=%s timestamp=%s",
        outcome,
        username,
        client_ip(),
        datetime.now(timezone.utc).isoformat(),
    )


@app.get("/")
def index():
    if session.get("username"):
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(LOGIN_TEMPLATE, error="")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if USERS.get(username) == password:
        session["username"] = username
        log_login_event("success", username)
        return redirect("/dashboard")

    log_login_event("failure", username)
    return render_template_string(LOGIN_TEMPLATE, error="Invalid username or password."), 401


@app.get("/dashboard")
def dashboard():
    username = session.get("username")
    if not username:
        return redirect("/login")
    return {
        "message": "Welcome to Northstar Payroll.",
        "user": username,
        "flag": "MAYAJAL{weak_password_payroll_access}",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
