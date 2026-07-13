"""PythonAnywhere WSGI shim.

PA's default WSGI file does:
    from flask_app import app as application

This module forwards to the real application in app.py so you only need to
fix PROJECT_HOME in the WSGI file (or point Source code at this repo).
"""
from app import app  # noqa: F401

__all__ = ['app']
