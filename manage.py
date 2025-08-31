#!/usr/bin/env python
"""
This is the entry point for the Django project.  It sets the default settings
module to ``hospital.settings`` and then delegates to Django's management
command line utility.  This file mirrors the default ``manage.py`` that
``django-admin startproject`` generates.
"""
import os
import sys


def main() -> None:
    """Run administrative tasks for the Django project."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital.settings')
    try:
        from django.core.management import execute_from_command_line  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()