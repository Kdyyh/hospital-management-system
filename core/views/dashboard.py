"""
Administrative dashboard endpoint.

Provides a high level overview of patient statuses and alerts.  Only
administrative roles (admin/core/super) may access this endpoint.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..permissions import IsAdminRole
from ..models import PatientProfile


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_dashboard(request):
    """Return dashboard metrics for administrators.

    The response structure matches the front‑end mock: numbers of
    patients waiting, in hospital and lost and a list of alert
    messages.  Alerts are currently generated statically but could be
    enhanced to reflect real system warnings.
    """
    # Compute patient statistics.  Filter by the requesting user's group
    # binding if present.  This ensures administrators only see data for
    # their department.
    user = request.user
    qs = PatientProfile.objects.all()
    if user.group:
        qs = qs.filter(group=user.group)
    waiting = qs.filter(status__icontains='等待').count()
    in_hospital = qs.filter(status__icontains='在院').count()
    lost = qs.filter(status__icontains='流失').count()
    # Example alert – in a real system this could come from a monitor
    alerts = [
        {
            'id': 'al1',
            'title': '病区已满',
            'desc': '部分病区接近上限',
            'time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    ]
    return Response({
        'waiting': waiting,
        'inHospital': in_hospital,
        'lost': lost,
        'alerts': alerts,
    })