"""
Custom authentication backend for token-based auth.

This module defines a subclass of Django REST framework's
``TokenAuthentication`` that simply overrides the ``keyword`` used in
the ``Authorization`` header.  By keeping this logic separate from any
view definitions we avoid circular import issues when the REST
framework imports authentication classes during initialization.
"""
from __future__ import annotations

from rest_framework import authentication


class TokenAuthentication(authentication.TokenAuthentication):
    """Custom token authentication using the ``Token`` keyword.

    DRF's default token authentication class also uses ``Token`` as the
    keyword.  This subclass exists to provide a stable import path for
    the project's configuration and to allow later customisation.
    """

    keyword = 'Token'
