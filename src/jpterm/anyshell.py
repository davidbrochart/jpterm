"""Expose jpterm's shared Cyclopts command tree to Anyshell."""


def register(session):
    from anyshell import Command

    from .cli import app

    session.register(Command("jpterm", "Jupyter document and kernel commands.", app.meta))
