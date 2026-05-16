"""SSL helpers for live HTTP clients on macOS/Python builds without system CAs."""

from __future__ import annotations

import ssl

import certifi


def default_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())
