"""Shared helpers for the server-rendered pages.

The JSON API answers an unauthenticated request with 401 through Flask-Login's
``login_required``. The browser pages instead send the visitor to the login
page, so they use :func:`login_page_required` and leave the API untouched.
"""

from functools import wraps

from flask import redirect, url_for
from flask_login import current_user


def anonymous_redirect():
    """The login redirect an unauthenticated page visitor should receive."""
    return redirect(url_for("auth.login"))


def login_page_required(view):
    """Send anonymous visitors to the login page before running *view*."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return anonymous_redirect()
        return view(*args, **kwargs)

    return wrapped
