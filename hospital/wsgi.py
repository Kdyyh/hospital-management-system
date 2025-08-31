"""
WSGI config for hospital project.

It exposes the WSGI callable as a module-level variable named ``application``.

This file was generated manually to avoid depending on ``django-admin``
during project bootstrap.  See Django documentation for more details.
"""
import os

from django.core.wsgi import get_wsgi_application  # type: ignore

# Set the default settings module for the 'django' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital.settings')

# Obtain the WSGI application for use by the server
application = get_wsgi_application()