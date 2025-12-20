"""WSGI entrypoint for production servers (e.g. Gunicorn).

Example:
  gunicorn -w 2 -b 0.0.0.0:5051 wsgi:app
"""

from app import create_app

app = create_app()
