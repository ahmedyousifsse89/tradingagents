"""Bearer-token auth for the control API.

This API can move money, so it fails closed in both directions: the app
refuses to start without a token configured, and every request without a
matching token is rejected. There is no "development mode" bypass — an
accidentally public instance with a trading-enabled Alpaca key is the exact
outcome this file exists to prevent.
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

TOKEN_ENV = "TRADINGAGENTS_API_TOKEN"
MIN_TOKEN_LENGTH = 24


class MissingAPIToken(RuntimeError):
    """Raised at startup when no usable API token is configured."""


def load_token(env: Optional[dict] = None) -> str:
    """Read and sanity-check the API token, raising when it is unusable."""
    source = env if env is not None else os.environ
    token = (source.get(TOKEN_ENV) or "").strip()
    if not token:
        raise MissingAPIToken(
            f"{TOKEN_ENV} is not set. The control API can place trades and will "
            f"not start without a token. Generate one with: "
            f"python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    if len(token) < MIN_TOKEN_LENGTH:
        raise MissingAPIToken(
            f"{TOKEN_ENV} must be at least {MIN_TOKEN_LENGTH} characters; "
            f"got {len(token)}"
        )
    return token


def token_matches(expected: str, presented: Optional[str]) -> bool:
    """Constant-time comparison of a presented bearer token."""
    if not presented:
        return False
    scheme, _, value = presented.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return False
    return hmac.compare_digest(expected, value.strip())
