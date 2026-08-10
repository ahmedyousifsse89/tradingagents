"""HTTP control plane for the trading bot (optional ``server`` extra)."""

from .auth import MissingAPIToken, load_token, token_matches

__all__ = ["MissingAPIToken", "load_token", "token_matches", "create_app"]


def __getattr__(name):
    # create_app imports FastAPI, which lives behind the optional extra.
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
