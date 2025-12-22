from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .routes import bp as routes_bp
from .auth_routes import auth_bp
from .farm_routes import farm_bp
from .application_log_routes import app_log_bp
from .auth import get_current_user_email


def create_app() -> Flask:
    # This package lives in `web_application_nys/app/`, while templates/static
    # live at `web_application_nys/templates` and `web_application_nys/static`.
    root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )

    # Session configuration (required for authentication)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Make user email available to all templates
    @app.context_processor
    def inject_user():
        return {"user_email": get_current_user_email()}

    # Routes
    app.register_blueprint(routes_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(farm_bp)
    app.register_blueprint(app_log_bp)

    return app
