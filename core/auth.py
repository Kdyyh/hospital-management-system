"""
Backward compatibility module for authentication.

This module preserves the previous import paths for ``TokenAuthentication``
and ``login_view`` while delegating to the new modules that avoid circular
imports.  Any additional utilities previously exposed are re-exported
from their new locations.  The rest of the project should import these
objects from this module so that changes to their implementation can be
centralised.
"""

from .authentication import TokenAuthentication
from .auth_views import (
    login_view,
    LoginSerializer,
    get_user_for_request,
    get_group_binding_for_user,
)

__all__ = [
    'TokenAuthentication',
    'login_view',
    'LoginSerializer',
    'get_user_for_request',
    'get_group_binding_for_user',
]