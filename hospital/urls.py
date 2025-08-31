"""
URL configuration for the hospital backend project.

The `urlpatterns` list routes URLs to views.  This module includes
both the Django admin and the API routes provided by the core app.
OpenAPI documentation is exposed at ``/swagger/`` and ``/redoc/``.
"""
from django.contrib import admin
from django.urls import path, include

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# API metadata for Swagger/OpenAPI documentation
api_info = openapi.Info(
    title="Hospital Backend API",
    default_version='v1',
    description="Backend services for the hospital management system.",
)

schema_view = get_schema_view(
    api_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Django admin site (useful for development)
    path('admin/', admin.site.urls),
    # Include API routes from the core app
    path('', include('core.routers')),
    # Swagger and ReDoc
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]