"""
Advertising text endpoint.

This simple resource stores a single advertisement or announcement
string which can be read by any authenticated user and updated by
administrators.
"""
from __future__ import annotations

from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Ad
from ..permissions import IsAdminRole


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ads(request):
    """Return the current advertisement text."""
    ad = Ad.objects.first()
    return Response({'text': ad.text if ad else ''})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def update_ads(request):
    """Update the advertisement text.

    Only administrators may perform this action.
    """
    text = request.data.get('text', '')
    with transaction.atomic():
        ad, _ = Ad.objects.get_or_create(pk=1)
        ad.text = text
        ad.save()
    return Response(True)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def delete_ads(request):
    """Delete the advertisement entry.

    This allows administrators to remove the current advertisement text entirely.
    If no advertisement exists, this is a no‑op.  Returns True on success.
    """
    with transaction.atomic():
        Ad.objects.all().delete()
    return Response(True)