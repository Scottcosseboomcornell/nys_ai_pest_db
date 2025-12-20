#!/usr/bin/env python3
"""Dev entrypoint for the NYS Flask app.

Uses Flask's built-in dev server with auto-reload.
"""

import os

from app import create_app


def main() -> None:
    app = create_app()

    # Dev defaults
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5051"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
