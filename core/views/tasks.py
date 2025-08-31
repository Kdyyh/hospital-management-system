"""
Task management views.

These endpoints provide CRUD operations for :class:`Task`.  Tasks are
restricted to group boundaries: administrators can only see and
manipulate tasks belonging to their own group, while super/core
administrators can operate across all groups.  Patients may only view
tasks they created or are assigned to.  Information leakage between
groups is prevented by enforcing these rules in every handler.
"""
from __future__ import annotations

from django.db import transaction, models
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Task, User, Group


def _serialize(task: Task) -> dict:
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'createdAt': task.created_at.isoformat() if task.created_at else None,
        'updatedAt': task.updated_at.isoformat() if task.updated_at else None,
        'groupId': task.group.id if task.group else None,
        'createdBy': task.created_by.id if task.created_by else None,
        'createdByName': task.created_by.get_full_name() if task.created_by else None,
        'assignedTo': task.assigned_to.id if task.assigned_to else None,
        'assignedToName': task.assigned_to.get_full_name() if task.assigned_to else None,
    }


def _can_access(user: User, task: Task) -> bool:
    if user.role in ('super', 'core'):
        return True
    if user.role == 'admin' and user.group_id and task.group_id == user.group_id:
        return True
    if user.role == 'patient' and (task.created_by_id == user.id or task.assigned_to_id == user.id):
        return True
    return False


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tasks_list(request):
    user: User = request.user
    if request.method == 'GET':
        qs = Task.objects.all()
        if user.role in ('super', 'core'):
            pass
        elif user.role == 'admin':
            qs = qs.filter(group_id=user.group_id or '')
        else:
            qs = qs.filter(models.Q(created_by=user) | models.Q(assigned_to=user))
        return Response([_serialize(t) for t in qs.order_by('-created_at')])
    # POST
    if user.role not in ('admin', 'core', 'super'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'detail': 'title is required'}, status=status.HTTP_400_BAD_REQUEST)
    description = request.data.get('description', '').strip()
    status_val = request.data.get('status', 'pending')
    assigned_id = request.data.get('assignedTo') or request.data.get('assigned_to')
    group_id = request.data.get('groupId') or request.data.get('group_id')
    with transaction.atomic():
        assigned = None
        if assigned_id:
            assigned = User.objects.filter(id=assigned_id).first()
        group = None
        if group_id:
            group = Group.objects.filter(id=group_id).first()
        elif user.group_id:
            group = user.group
        task = Task.objects.create(
            title=title,
            description=description,
            status=status_val if status_val in dict(Task.STATUS_CHOICES) else 'pending',
            created_by=user,
            assigned_to=assigned,
            group=group,
        )
    return Response(_serialize(task), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def task_detail(request, pk: int):
    user: User = request.user
    task = get_object_or_404(Task, pk=pk)
    if not _can_access(user, task):
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        return Response(_serialize(task))
    if request.method == 'PUT':
        if user.role not in ('admin', 'core', 'super') and task.created_by_id != user.id:
            return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        data = request.data
        with transaction.atomic():
            title = data.get('title')
            description = data.get('description')
            status_val = data.get('status')
            assigned_id = data.get('assignedTo') or data.get('assigned_to')
            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if status_val is not None and status_val in dict(Task.STATUS_CHOICES):
                task.status = status_val
            if assigned_id is not None:
                task.assigned_to = User.objects.filter(id=assigned_id).first()
            task.save()
        return Response(_serialize(task))
    # DELETE
    if user.role not in ('admin', 'core', 'super') and task.created_by_id != user.id:
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    task.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)