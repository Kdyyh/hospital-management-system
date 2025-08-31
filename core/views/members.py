"""
Group member management endpoints.

These views allow administrative users to add members to groups,
promote/demote them and remove them.  Quotas are enforced at the
group level.
"""
from __future__ import annotations

from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Group, GroupMember, User
from ..permissions import IsAdminRole


def _ensure_space(group: Group) -> bool:
    """Return True if the group has capacity for another member."""
    return group.members.count() < (group.quota or 0)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def add_from_pool(request):
    """Add a member from the user pool to a group.

    Expects ``groupId`` and ``account``.  Creates the user if
    necessary.  Fails if the group quota is exceeded.
    """
    group_id = request.data.get('groupId')
    account = request.data.get('account')
    if not group_id or not account:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=group_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if not _ensure_space(group):
        return Response({'detail': 'group full'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        user, created = User.objects.get_or_create(username=account)
        if created:
            user.set_password('password123')
        user.role = 'member'
        user.group = group
        user.group_bind_time = timezone.now()
        user.save()
        GroupMember.objects.update_or_create(group=group, user=user, defaults={'role': 'member'})
    return Response({'ok': True, 'message': '成员添加成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def add_member(request):
    """Add an existing user to a group by UID."""
    group_id = request.data.get('groupId')
    uid = request.data.get('uid')
    name = request.data.get('name')
    if not group_id or not uid or not name:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=group_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if not _ensure_space(group):
        return Response({'detail': 'group full'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        user, created = User.objects.get_or_create(username=uid, defaults={'first_name': name})
        if created:
            user.set_password('password123')
        user.group = group
        user.group_bind_time = timezone.now()
        user.save()
        GroupMember.objects.update_or_create(group=group, user=user, defaults={'role': 'member'})
    return Response({'ok': True, 'message': '成员添加成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def set_leader(request):
    """Promote a member to leader within a group."""
    group_id = request.data.get('groupId')
    uid = request.data.get('uid')
    group = Group.objects.filter(id=group_id).first()
    user = User.objects.filter(username=uid).first()
    if not group or not user:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    membership = GroupMember.objects.filter(group=group, user=user).first()
    if not membership:
        return Response({'detail': 'member not found'}, status=status.HTTP_404_NOT_FOUND)
    membership.role = 'leader'
    membership.save()
    return Response({'ok': True, 'message': '组长设置成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def set_role(request):
    if getattr(request.user, 'role', '') != 'super':
        from rest_framework.response import Response
        from rest_framework import status
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    """Set a member's role within a group."""
    group_id = request.data.get('groupId')
    uid = request.data.get('uid')
    role = request.data.get('role')
    if role not in ('member','admin','core','super'):
        return Response({'detail': 'invalid role'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(id=group_id).first()
    user = User.objects.filter(username=uid).first()
    if not group or not user:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    membership = GroupMember.objects.filter(group=group, user=user).first()
    if not membership:
        return Response({'detail': 'member not found'}, status=status.HTTP_404_NOT_FOUND)
    membership.role = role
    membership.save()
    return Response({'ok': True, 'message': '角色设置成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def remove_member(request):
    """Remove a user from a group."""
    group_id = request.data.get('groupId')
    uid = request.data.get('uid')
    group = Group.objects.filter(id=group_id).first()
    user = User.objects.filter(username=uid).first()
    if not group or not user:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    GroupMember.objects.filter(group=group, user=user).delete()
    # Clear binding if necessary
    if user.group == group:
        user.group = None
        user.group_bind_time = None
        user.save()
    return Response({'ok': True, 'message': '成员移除成功'})