"""
Group (department/expert group) related endpoints.

These views allow clients to list, create and manage groups, bind
users to groups via invite codes, manage membership and quotas and
query the current binding.  Most operations require an administrative
role; binding/unbinding is available to any authenticated user.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from ..models import Group, GroupMember, User
from ..permissions import IsAdminRole


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_groups(request):
    """Return all groups."""
    groups = Group.objects.all()
    data = []
    for g in groups:
        data.append({
            'id': g.id,
            'name': g.name,
            'open': g.open,
            'quota': g.quota,
            'inviteCode': g.invite_code,
            'description': g.description,
            'specialties': g.specialties,
            'createdAt': int(g.created_at.timestamp()),
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def create_group(request):
    """Create a new group."""
    name = request.data.get('name') or ''
    quota = int(request.data.get('quota') or 0)
    invite_code = request.data.get('inviteCode') or ''
    description = request.data.get('description') or ''
    specialties = request.data.get('specialties') or []
    # Generate identifier
    index = Group.objects.count() + 1
    new_id = f'g{index}'
    group = Group.objects.create(
        id=new_id,
        name=name,
        quota=quota,
        invite_code=invite_code,
        description=description,
        specialties=specialties,
        open=True,
    )
    return Response({'id': group.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def open_group(request):
    """Toggle a group's open state."""
    group_id = request.data.get('id')
    group = Group.objects.filter(id=group_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    group.open = not group.open
    group.save()
    return Response({'open': group.open})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def set_quota(request):
    """Set the quota for a group."""
    group_id = request.data.get('id')
    quota = request.data.get('quota')
    group = Group.objects.filter(id=group_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if quota is not None:
        group.quota = int(quota)
        group.save()
    return Response({'quota': group.quota})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_by_code(request):
    """Look up a group by invite code.

    Returns group information if the code matches a group and the group
    is open.  This does not bind the user; it merely validates the
    invite.
    """
    invite_id = request.data.get('invite_id') or request.data.get('inviteId') or request.data.get('code')
    if not invite_id:
        return Response({'detail': 'invalid code'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(invite_code=invite_id).first()
    if not group:
        return Response({'detail': 'invalid invite'}, status=status.HTTP_404_NOT_FOUND)
    if not group.open:
        return Response({'detail': 'group closed'}, status=status.HTTP_403_FORBIDDEN)
    # Build group info
    leader = group.members.filter(role='leader').select_related('user').first()
    return Response({
        'success': True,
        'data': {
            'id': group.id,
            'name': group.name,
            'inviteCode': group.invite_code,
            'description': group.description,
            'department': group.name,
            'leader': leader.user.get_full_name() if leader else '',
            'specialties': group.specialties,
            'memberCount': group.members.count(),
            'quota': group.quota,
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_binding(request):
    """Bind the current user to a group."""
    group_id = request.data.get('groupId') or request.data.get('id')
    group = Group.objects.filter(id=group_id).first()
    if not group:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if request.user.group:
        return Response({'detail': 'already bound'}, status=status.HTTP_409_CONFLICT)
    request.user.group = group
    request.user.group_bind_time = timezone.now()
    request.user.save()
    return Response({
        'success': True,
        'message': '成功加入专家组',
        'binding': {
            'groupId': group.id,
            'groupName': group.name,
            'bindTime': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_binding(request):
    """Return the current user's group binding."""
    user: User = request.user  # type: ignore[assignment]
    if not user.group:
        return Response({'bound': False})
    group = user.group
    leader = group.members.filter(role='leader').select_related('user').first()
    return Response({
        'bound': True,
        'groupId': group.id,
        'groupName': group.name,
        'inviteCode': group.invite_code,
        'bindTime': (user.group_bind_time or timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
        'groupInfo': {
            'description': group.description,
            'specialties': group.specialties,
            'memberCount': group.members.count(),
            'quota': group.quota,
            'leader': leader.user.get_full_name() if leader else '',
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unbind_group(request):
    """Unbind the current user from their group."""
    if request.user.group:
        request.user.group = None
        request.user.group_bind_time = None
        request.user.save()
    return Response({'success': True, 'message': '已成功解除科室绑定'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def invites(request):
    """Group invites endpoint.

    The front‑end reuses the same path for creating and listing group
    invites, distinguishing the operation by the HTTP method.  To
    align with the API contract defined in the mini‑program, this
    view now supports both ``GET`` and ``POST``.

    * ``GET`` – Return a list of available invites.  This is a
      simplified implementation which enumerates all groups and
      returns their existing invite codes.  In a real system you
      would filter by the requesting administrator's scope and
      include metadata such as expiration time or usage limits.

    * ``POST`` – Create a new invite.  For the purposes of this
      mock implementation we simply acknowledge the request.  The
      front‑end can supply parameters such as ``groupId`` or
      ``expiresAt`` in the body which would be used to generate a
      unique invite code and persist it.
    """
    # Listing invites
    if request.method == 'GET':
        # Determine which groups the admin can see.  If the admin
        # is bound to a group we list only that group; otherwise we
        # return all groups.  Each invite entry contains the group
        # ID and current invite code.  Additional fields can be added
        # as needed.
        from ..models import Group  # inline import to avoid cycles
        user = request.user  # type: ignore[assignment]
        qs = Group.objects.all()
        if user.group:
            qs = qs.filter(id=user.group.id)
        invites_data = []
        for g in qs:
            invites_data.append({
                'groupId': g.id,
                'groupName': g.name,
                'inviteCode': g.invite_code,
                'createdAt': g.created_at.strftime('%Y-%m-%d %H:%M'),
            })
        return Response({'invites': invites_data})
    # Creating an invite (POST)
    # In a real implementation you would generate a new unique code,
    # associate it with the specified group and return the new entry.
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bind_by_invite(request):
    """Bind to a group via invite code.

    Accepts ``invite_id`` (or ``inviteId``) and an optional
    ``action`` parameter (e.g. ``bind``).  This endpoint validates
    the invite code and returns the corresponding group information.
    Binding is deferred to the ``confirm_binding`` endpoint so that
    the front‑end can display a confirmation dialog before
    persisting the association.  If ``action`` equals ``bind`` and
    the user is already bound to a group a ``409 Conflict`` is
    returned.  Additional HTTP methods (e.g. GET) are not supported
    here because invites are listed via the ``invites`` endpoint.
    """
    invite_id = request.data.get('invite_id') or request.data.get('inviteId') or request.data.get('code')
    action = request.data.get('action') or ''
    if not invite_id:
        return Response({'detail': 'invalid code'}, status=status.HTTP_400_BAD_REQUEST)
    group = Group.objects.filter(invite_code=invite_id).first()
    if not group:
        return Response({'detail': 'invalid invite'}, status=status.HTTP_404_NOT_FOUND)
    # Check if the user is already bound when attempting to bind
    if action == 'bind' and request.user.group:
        return Response({'detail': 'already bound'}, status=status.HTTP_409_CONFLICT)
    return Response({
        'success': True,
        'data': {
            'id': group.id,
            'name': group.name,
            'inviteCode': group.invite_code,
            'description': group.description,
            'department': group.name,
            'leader': group.members.filter(role='leader').select_related('user').first().user.get_full_name() if group.members.filter(role='leader').exists() else '',
            'specialties': group.specialties,
            'memberCount': group.members.count(),
            'quota': group.quota,
        },
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def transfer_requests(request):
    """Group transfer requests endpoint.

    This view supports both listing and creating transfer requests on
    the same path (``/api/groups/transfer-requests``).  The front‑end
    uses a ``GET`` request to retrieve pending transfer requests and
    a ``POST`` request to submit a new transfer request.  The
    simplified implementation below returns mock data for listing
    and acknowledges creation requests.
    """
    # Listing transfer requests
    if request.method == 'GET':
        # In a real system you would query the database for pending
        # requests filtered by the administrator's scope.  Here we
        # return a static list for demonstration purposes.
        mock_requests = [
            {
                'requestId': 'transfer_1',
                'fromGroupId': 'g1',
                'toGroupId': 'g2',
                'patientId': 'p123',
                'status': 'pending',
                'createdAt': timezone.now().strftime('%Y-%m-%d %H:%M'),
            },
        ]
        return Response({'requests': mock_requests})
    # Creating a transfer request
    # The front‑end may provide ``fromGroupId``, ``toGroupId`` and
    # ``patientId``.  We simply return a generated request ID and
    # mark the status as pending.  A real implementation would
    # persist this request and notify administrators.
    request_id = f'transfer_{int(timezone.now().timestamp())}'
    return Response({
        'success': True,
        'message': '转组申请已提交，等待管理员审核',
        'data': {
            'requestId': request_id,
            'status': 'pending',
        },
    })