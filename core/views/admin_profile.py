"""
Administrative profile and miscellaneous endpoints.

This module provides endpoints to read and update the administrator's
profile and to fetch audit logs and grant permissions.  These are
largely stubs to match the front‑end API contract.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..permissions import IsAdminRole


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_profile_get(request):
    """Return the current administrator's profile."""
    user = request.user
    return Response({
        'name': user.get_full_name() or user.username,
        'role': user.role,
        'department': user.group.name if user.group else '',
        'phone': '',
        'email': '',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_profile_update(request):
    """Update the current administrator's profile."""
    user = request.user
    name = request.data.get('name')
    phone = request.data.get('phone')
    email = request.data.get('email')
    if name:
        # Update first_name for display name
        user.first_name = name
    # phone/email stored nowhere but could be saved in extended model
    user.save()
    return Response({'ok': True, 'message': '资料更新成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_update(request):
    """Generic update endpoint stub."""
    return Response({'ok': True, 'message': '更新成功'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def report_log(request):
    """Return a static list of audit logs."""
    logs = [
        {'id': 'log1', 'type': 'login', 'user': '管理员A', 'time': '2025-08-20 10:30', 'detail': '登录系统'},
        {'id': 'log2', 'type': 'operation', 'user': '核心管C', 'time': '2025-08-20 09:15', 'detail': '更新科室信息'},
        {'id': 'log3', 'type': 'error', 'user': '系统', 'time': '2025-08-19 16:45', 'detail': '数据库连接超时'},
    ]
    return Response(logs)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def grant(request):
    """Stub for granting permissions."""
    return Response({'ok': True, 'message': '权限授予成功'})