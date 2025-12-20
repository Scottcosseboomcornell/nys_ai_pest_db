from __future__ import annotations

from pathlib import Path

from flask import Flask

from .routes import bp as routes_bp


def create_app() -> Flask:
    # This package lives in `web_application_nys/app/`, while templates/static
    # live at `web_application_nys/templates` and `web_application_nys/static`.
    root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )

    # Routes
    app.register_blueprint(routes_bp)

    return app
