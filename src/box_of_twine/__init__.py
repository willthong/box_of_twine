import os
from pathlib import Path

from flask import Flask

from . import db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE=str(Path(app.instance_path) / "box_of_twine.sqlite"),
        DATA_DIR=os.environ.get("DATA_DIR", "/data"),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD"),
        LOCK_LEASE_SECONDS=600,
    )
    if test_config is not None:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from .auth import bp as auth_bp
    from .auth import login_manager
    from .prefs import bp as prefs_bp
    from .publications import bp as publications_bp
    from .stories import bp as stories_bp
    from .users import bp as users_bp
    from .users import ensure_admin

    app.register_blueprint(auth_bp)
    app.register_blueprint(prefs_bp)
    app.register_blueprint(publications_bp)
    app.register_blueprint(stories_bp)
    app.register_blueprint(users_bp)
    login_manager.init_app(app)

    with app.app_context():
        ensure_admin(app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])

    return app
