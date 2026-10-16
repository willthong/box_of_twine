from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user

from .prefs import current_theme
from .users import get_user_by_id, get_user_by_username, verify_password

bp = Blueprint("auth", __name__)
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id: str):
    return get_user_by_id(int(user_id))


@bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if user is None or not verify_password(user, password) or not user.is_active:
            return render_template("login.html", theme=current_theme()), 401
        login_user(user)
        return redirect(url_for("stories.home"))
    return render_template("login.html", theme=current_theme())
