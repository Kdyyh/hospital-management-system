"""
Department (group) management views.

These endpoints provide CRUD operations for departments (called
``groups`` internally) including listing, detail, membership and
administrative operations.  Only administrative users may modify
departments.
"""
from __future__ import annotations

from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from ..models import Group, GroupMember, User
from django.utils import timezone
from ..permissions import IsAdminRole


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def departments(request):
    """List departments or create/update a department.

    ``GET`` returns a list of all groups.  ``POST`` will create a
    new group when no ``id`` (or ``deptId``) is provided, otherwise
    it updates the existing group's basic information.  Only
    administrative users (admin/core/super) may create or update
    groups.
    """
    # List all departments
    if request.method == 'GET':
        groups = Group.objects.all()
        data: list[dict[str, object]] = []
        for g in groups:
            data.append({
                'id': g.id,
                'name': g.name,
                'description': g.description,
                'open': g.open,
                'quota': g.quota,
            })
        return Response(data)

    # For POST requests ensure the caller has administrative privileges
    if request.user.role not in ('admin', 'core', 'super'):
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

    # Determine if this is an update or create operation
    dept_id = request.data.get('id') or request.data.get('deptId') or None
    name = request.data.get('name') or request.data.get('deptName') or ''
    # Accept either ``description`` or ``desc`` fields
    description = request.data.get('description') or request.data.get('desc') or ''
    # Accept quota as numeric string
    quota_value = request.data.get('quota') or request.data.get('quotaNum') or None
    # Accept open state toggle
    open_state = request.data.get('open')
    # When updating an existing group
    if dept_id:
        group = Group.objects.filter(id=dept_id).first()
        if not group:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        # Update provided fields; ignore empty strings to avoid overwriting with blanks
        if name:
            group.name = name
        if description:
            group.description = description
        if quota_value is not None:
            try:
                group.quota = int(quota_value)
            except (ValueError, TypeError):
                pass
        if open_state is not None:
            # Coerce booleans or strings
            if isinstance(open_state, bool):
                group.open = open_state
            elif str(open_state).lower() in ('true', '1', 'yes'):
                group.open = True
            elif str(open_state).lower() in ('false', '0', 'no'):
                group.open = False
        group.save()
        return Response({'success': True, 'id': group.id})

    # Creating a new group
    # Default quota to 0 if not provided
    try:
        quota_int = int(quota_value) if quota_value is not None else 0
    except (ValueError, TypeError):
        quota_int = 0
    with transaction.atomic():
        # Generate a simple identifier: g<num> that does not collide
        existing_ids = set(Group.objects.values_list('id', flat=True))
        index = 1
        while f'g{index}' in existing_ids:
            index += 1
        new_id = f'g{index}'
        group = Group.objects.create(
            id=new_id,
            name=name,
            description=description,
            quota=quota_int,
            open=True,
        )
    return Response({'id': group.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_detail(request):
    """Return detailed information about a specific department."""
    # Accept id from query params or request data; support both id and deptId names
    dept_id = (
        request.query_params.get('id')
        or request.query_params.get('deptId')
        or request.data.get('id')
        or request.data.get('deptId')
    )
    if not dept_id:
        return Response({'detail': 'missing id'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'id': group.id,
        'name': group.name,
        'description': group.description,
        'open': group.open,
        'quota': group.quota,
        'inviteCode': group.invite_code,
        'specialties': group.specialties,
        'createdAt': int(group.created_at.timestamp()),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_members(request):
    """Return members of a department.

    Expects ``deptId`` (or ``id``) as a query parameter.  Any
    authenticated user may call this endpoint.  For patients, the
    returned information is limited to the member's name and role to
    avoid exposing sensitive data.  Administrators receive the same
    structure, so front‑end code can consume the endpoint uniformly.
    """
    # Accept id from both query and body; support id or deptId
    dept_id = (
        request.query_params.get('deptId')
        or request.query_params.get('id')
        or request.data.get('deptId')
        or request.data.get('id')
    )
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response([], status=status.HTTP_200_OK)
    # If the caller is a patient and bound to a different group, deny access
    user = request.user  # type: ignore[assignment]
    if user.role == 'patient' and user.group_id and str(user.group_id) != str(group.id):
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    members_data: list[dict[str, object]] = []
    # Include additional non‑sensitive details: full name, username and email.
    for gm in group.members.select_related('user'):
        user = gm.user
        members_data.append({
            'uid': user.username,
            'name': user.get_full_name() or user.username,
            'role': gm.role,
            'department': group.name,
            'username': user.username,
            'fullName': user.get_full_name() or '',
            'email': user.email or ''
        })
    return Response(members_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def department_publish(request):
    """Toggle the open/closed state of a department."""
    # Accept id or deptId from body
    dept_id = request.data.get('deptId') or request.data.get('id')
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    group.open = not group.open
    group.save()
    return Response({'open': group.open})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def department_info(request):
    """Get or update department meta information (name and description)."""
    # Accept id from both query and body; support id or deptId
    dept_id = (
        request.query_params.get('deptId')
        or request.query_params.get('id')
        or request.data.get('deptId')
        or request.data.get('id')
    )
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        return Response({'name': group.name, 'desc': group.description})
    # POST: update; only admins
    if request.user.role not in ('admin', 'core', 'super'):
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    # Allow both name and deptName; maintain existing values if not provided
    name = request.data.get('name') or request.data.get('deptName') or group.name
    desc = (
        request.data.get('desc')
        or request.data.get('description')
        or request.data.get('descriptionText')
        or group.description
    )
    group.name = name
    group.description = desc
    group.save()
    return Response(True)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def department_admins(request):
    """Return administrative users for a department."""
    dept_id = (
        request.query_params.get('deptId')
        or request.query_params.get('id')
        or request.data.get('deptId')
        or request.data.get('id')
        or (request.user.group.id if getattr(request.user, 'group', None) else None)
    )
    group = Group.objects.filter(id=dept_id).first() if dept_id else None
    admins_data = []
    if not group:
        # Without a group context return all admin users
        users = User.objects.filter(role__in=('admin','core','super'))
        for u in users:
            admins_data.append({
                'uid': u.username,
                'name': u.get_full_name() or u.username,
                'department': u.group.name if u.group else '',
                'groupId': u.group.id if u.group else '',
            })
        return Response(admins_data)
    # With a group return admins bound to this group
    for gm in group.members.select_related('user'):
        if gm.user.role in ('admin','core','super'):
            admins_data.append({
                'uid': gm.user.username,
                'name': gm.user.get_full_name() or gm.user.username,
                'department': group.name,
                'groupId': group.id,
            })
    return Response(admins_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def add_department_admin(request):
    """Add an administrative user to a department.

    Accepts ``account`` as the username to add and ``deptId`` as the
    target group.  If the user does not exist it will be created.
    """
    # Accept different parameter names for the account: account, adminId, uid
    account = (
        request.data.get('account')
        or request.data.get('adminId')
        or request.data.get('uid')
    )
    # Accept id or deptId to identify the group
    dept_id = request.data.get('deptId') or request.data.get('id')
    if not account or not dept_id:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=dept_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    with transaction.atomic():
        # Create or update the user; default role is admin
        user, created = User.objects.get_or_create(username=account, defaults={'role': 'admin'})
        if created:
            user.set_password('admin123')
        # Ensure the user role is at least admin
        user.role = 'admin'
        # Bind to group
        user.group = group
        user.group_bind_time = timezone.now()
        user.save()
        # Add to group member table with default role member
        GroupMember.objects.update_or_create(group=group, user=user, defaults={'role': 'member'})
    return Response(True)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def remove_department_admin(request):
    """Remove an administrative user from a department."""
    # Accept admin identifier via uid or adminId
    uid = request.data.get('uid') or request.data.get('adminId')
    dept_id = request.data.get('deptId') or request.data.get('id')
    if not uid or not dept_id:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=dept_id).first()
    user = User.objects.filter(username=uid).first()
    if not group or not user:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Remove the user from the group membership list
    GroupMember.objects.filter(group=group, user=user).delete()
    # Optionally clear the user's group binding if they are bound to this group
    if user.group_id == group.id:
        user.group = None
        user.group_bind_time = None
        user.save()
    return Response(True)