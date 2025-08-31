"""
User department binding views.

These endpoints implement the department (group) binding APIs expected
by the front‑end.  They allow users to bind themselves or another
user to a department, check their current binding and retrieve a list
of available departments.  The logic here wraps the existing group
model and provides responses that mirror the mock specification.

Endpoints provided:

* ``POST /api/user/bind-department`` – bind a user to a department.
  Accepts ``userId`` (optional; defaults to the authenticated user),
  ``departmentId`` or ``groupId`` and optionally ``role``.  Returns
  success information with the bound group details.

* ``GET /api/user/check-department-binding`` – return the current
  binding status for the authenticated user.  Indicates whether the
  user is bound to a department and echoes the group information.

* ``GET /api/user/available-departments`` – list all open
  departments.  The response includes the department's ID, name,
  description and a boolean ``isActive`` flag mirroring the
  ``open`` attribute on the underlying group.

The views use the existing ``Group`` and ``User`` models.  On a
successful bind the user's ``group`` field and ``group_bind_time``
timestamp are updated.  If the user has a patient profile the
``group`` on the related ``PatientProfile`` is also updated to
maintain consistency.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import User, Group


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bind_department(request):
    """Bind a user to a department.

    Accepts ``userId`` to specify a target user (defaults to the
    authenticated user) and ``departmentId`` or ``groupId`` to
    identify the department.  Updates the ``group`` and
    ``group_bind_time`` fields on the target user and synchronises
    the group on any associated patient profile.  Returns a payload
    indicating success along with the new binding information.
    """
    data = request.data or {}
    user_id = data.get('userId') or data.get('uid')
    dept_id = data.get('departmentId') or data.get('groupId')
    if not dept_id:
        return Response({'detail': 'missing departmentId'}, status=status.HTTP_400_BAD_REQUEST)
    # Determine the target user: if userId is provided and the caller
    # has the necessary privileges they can bind another user.  In this
    # simplified implementation we allow users to bind themselves or
    # administrators to bind any user.  Additional permission checks
    # (e.g. only admins may bind others) can be added here.
    if user_id:
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'user not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        target_user = request.user
    # Look up the group
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response({'detail': 'department not found'}, status=status.HTTP_404_NOT_FOUND)
    # Update the user's group and bind time
    now = timezone.now()
    target_user.group = group
    target_user.group_bind_time = now
    target_user.save(update_fields=['group', 'group_bind_time'])
    # Update patient profile group if applicable
    if hasattr(target_user, 'patient_profile') and target_user.patient_profile:
        pp = target_user.patient_profile
        pp.group = group
        pp.save(update_fields=['group'])
    return Response({
        'success': True,
        'message': '科室绑定成功',
        'data': {
            'departmentId': group.id,
            'departmentName': group.name,
            'groupId': group.id,
            'groupName': group.name,
            'bindTime': now.isoformat(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_department_binding(request):
    """Return the current binding status for the authenticated user.

    If the user is bound to a group the response includes the group
    identifier, name and bind time.  Otherwise the response simply
    indicates that no binding exists.
    """
    user = request.user
    group = user.group
    if group:
        return Response({
            'bound': True,
            'departmentId': group.id,
            'departmentName': group.name,
            'groupId': group.id,
            'groupName': group.name,
            'bindTime': user.group_bind_time.isoformat() if user.group_bind_time else None,
        })
    return Response({'bound': False})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_departments(request):
    """Return a list of available departments.

    Only departments marked as open are returned.  Each item includes
    the department's ID, name, description and an ``isActive`` flag
    which mirrors the group's ``open`` attribute.  A ``groupId``
    property is also included for backward compatibility, mapping to
    the same identifier.
    """
    groups = Group.objects.filter(open=True)
    data: list[dict[str, object]] = []
    for g in groups:
        data.append({
            'id': g.id,
            'name': g.name,
            'description': g.description,
            'isActive': g.open,
            'groupId': g.id,
        })
    return Response(data)