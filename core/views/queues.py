"""
Queue and queue item management endpoints.

These endpoints implement a simple queueing system for patients and
administrators.  Patients can view their place in the queue, cancel
their own entries and set priority levels.  Administrators have
broad control: they can view all queue items in their department,
update statuses (including completing an item which automatically
advances the next waiting item), set priority and broadcast
notifications.
"""
from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Queue, QueueItem, QueueItemTransition, User
from ..permissions import IsAdminRole, IsPatientRole


def _can_transition(current: str, new: str) -> bool:
    """Return True if the queue item may transition from ``current`` to ``new``."""
    transitions = {
        '等待中': ['就诊中', '已取消'],
        '就诊中': ['已完成', '已取消'],
        '已完成': [],
        '已取消': [],
    }
    return new in transitions.get(current, [])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def queue_status(request):
    """Return the high level queue status for the user's group.

    The response is a simple aggregate of the first queue in the user's
    group.  If multiple queues exist we use the first one alphabetically.
    If no queue is available the values default to zero or empty.
    """
    user: User = request.user  # type: ignore[assignment]
    queue = None
    if user.group:
        queue = Queue.objects.filter(group=user.group).order_by('id').first()
    if not queue:
        return Response({'currentNumber': 0, 'waitingCount': 0, 'estimatedTime': ''})
    return Response({
        'currentNumber': queue.current_number,
        'waitingCount': queue.waiting_count,
        'estimatedTime': queue.estimated_time,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_list(request):
    """Return a simplified list of active queue items for administrators."""
    user: User = request.user  # type: ignore[assignment]
    items = QueueItem.objects.select_related('queue', 'patient')
    if user.group:
        items = items.filter(queue__group=user.group)
    data: list[dict] = []
    for item in items.order_by('created_at')[:50]:
        data.append({
            'id': item.id,
            'name': item.patient.get_full_name() or item.patient.username,
            'number': item.number,
            'status': item.status,
            'department': item.queue.name,
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatientRole])
def queue_item_detail(request):
    """Return detailed information for a patient's own queue item."""
    queue_item_id = (
        request.query_params.get('id')
        or request.query_params.get('queueItemId')
        or request.data.get('id')
        or request.data.get('queueItemId')
    )
    item = QueueItem.objects.select_related('queue', 'patient').filter(id=queue_item_id).first()
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Verify the item belongs to the patient
    if item.patient != request.user:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    return Response({
        'id': item.id,
        'patientId': item.patient.username,
        'patientName': item.patient.get_full_name() or item.patient.username,
        'number': item.number,
        'status': item.status,
        'priority': item.priority,
        'department': item.queue.name,
        'groupId': item.queue.group.id if item.queue.group else None,
        'createdAt': item.created_at.strftime('%Y-%m-%d %H:%M'),
        'startedAt': item.started_at.strftime('%Y-%m-%d %H:%M') if item.started_at else None,
        'completedAt': item.completed_at.strftime('%Y-%m-%d %H:%M') if item.completed_at else None,
        'expectedTime': item.expected_time.strftime('%Y-%m-%d %H:%M') if item.expected_time else None,
        'transitionHistory': [
            {
                'from': t.from_status,
                'to': t.to_status,
                'operator': t.operator.username if t.operator else '',
                'timestamp': t.timestamp.strftime('%Y-%m-%d %H:%M'),
                'reason': t.reason,
            }
            for t in item.transitions.all().order_by('timestamp')
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatientRole])
def queue_item_update_status(request):
    """Allow a patient to update the status of their own queue item.

    Patients may only cancel their queue entry.  The request body
    accepts both legacy and modern parameter names: ``id`` or
    ``queueItemId`` to identify the queue item, and ``status`` or
    ``newStatus`` to specify the desired state.  Attempts to set other
    statuses or operate on another patient's item will result in an
    error.  Rows are locked during update to avoid race conditions.
    """
    queue_item_id = request.data.get('id') or request.data.get('queueItemId')
    new_status = request.data.get('status') or request.data.get('newStatus')
    reason = request.data.get('reason') or '状态更新'
    if not queue_item_id or not new_status:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    # Fetch with related objects early for permission checks
    item = (
        QueueItem.objects.select_related('queue', 'patient')
        .filter(id=queue_item_id)
        .first()
    )
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure the item belongs to the patient
    if item.patient != request.user:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    # Patients can only cancel their entry
    if new_status != '已取消':
        return Response({'detail': '患者只能取消排队'}, status=status.HTTP_403_FORBIDDEN)
    # Verify transition
    if not _can_transition(item.status, new_status):
        return Response({'detail': f'无法从 {item.status} 转换为 {new_status}'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        # Lock the item row for update
        locked_item = (
            QueueItem.objects.select_for_update().select_related('queue').get(id=item.id)
        )
        old_status = locked_item.status
        locked_item.status = new_status
        locked_item.completed_at = timezone.now() if new_status == '已完成' else locked_item.completed_at
        locked_item.save()
        QueueItemTransition.objects.create(
            item=locked_item,
            from_status=old_status,
            to_status=new_status,
            operator=request.user,
            reason=reason,
        )
        queue = locked_item.queue
        # Update waiting count after cancellation
        queue.waiting_count = queue.items.filter(status='等待中').count()
        queue.save()
    return Response({'success': True, 'newStatus': new_status})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatientRole])
def queue_item_set_priority(request):
    """Allow a patient to set the priority of their queue item."""
    queue_item_id = request.data.get('id') or request.data.get('queueItemId')
    priority = request.data.get('priority')
    if not queue_item_id or not priority:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    item = QueueItem.objects.select_related('patient').filter(id=queue_item_id).first()
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    if item.patient != request.user:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    if priority not in dict(QueueItem.PRIORITY_CHOICES).keys():
        return Response({'detail': '无效的优先级'}, status=status.HTTP_400_BAD_REQUEST)
    item.priority = priority
    item.save()
    return Response({'success': True, 'newPriority': priority})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def queue_list(request):
    """List queues accessible to the current user."""
    user: User = request.user  # type: ignore[assignment]
    qs = Queue.objects.all()
    if user.role == 'patient':
        # Patients see only their group's queues
        qs = qs.filter(group=user.group)
    elif user.group:
        qs = qs.filter(group=user.group)
    data: list[dict] = []
    for q in qs:
        data.append({
            'id': q.id,
            'name': q.name,
            'departmentId': q.department,
            'currentNumber': q.current_number,
            'waitingCount': q.waiting_count,
            'estimatedTime': q.estimated_time,
            'status': q.status,
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_item_detail(request):
    """Return detailed information for a queue item (admin view)."""
    queue_item_id = (
        request.query_params.get('id')
        or request.query_params.get('queueItemId')
        or request.data.get('id')
        or request.data.get('queueItemId')
    )
    item = QueueItem.objects.select_related('queue', 'patient').prefetch_related('transitions').filter(id=queue_item_id).first()
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure admin has access
    user: User = request.user  # type: ignore[assignment]
    if user.group and item.queue.group and item.queue.group != user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    # Build response similar to patient but with full history
    return Response({
        'id': item.id,
        'patientId': item.patient.username,
        'patientName': item.patient.get_full_name() or item.patient.username,
        'number': item.number,
        'status': item.status,
        'priority': item.priority,
        'department': item.queue.name,
        'groupId': item.queue.group.id if item.queue.group else None,
        'createdAt': item.created_at.strftime('%Y-%m-%d %H:%M'),
        'startedAt': item.started_at.strftime('%Y-%m-%d %H:%M') if item.started_at else None,
        'completedAt': item.completed_at.strftime('%Y-%m-%d %H:%M') if item.completed_at else None,
        'expectedTime': item.expected_time.strftime('%Y-%m-%d %H:%M') if item.expected_time else None,
        'transitionHistory': [
            {
                'from': t.from_status,
                'to': t.to_status,
                'operator': t.operator.username if t.operator else '',
                'timestamp': t.timestamp.strftime('%Y-%m-%d %H:%M'),
                'reason': t.reason,
            }
            for t in item.transitions.all().order_by('timestamp')
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_item_update_status(request):
    """Administrators update a queue item's status.

    Handles automatic progression when completing an item.  Accepts
    both legacy (``queueItemId``/``newStatus``) and simplified
    (``id``/``status``) parameter names.  Rows are locked while
    updating to avoid concurrent modifications.
    """
    queue_item_id = request.data.get('id') or request.data.get('queueItemId')
    new_status = request.data.get('status') or request.data.get('newStatus')
    reason = request.data.get('reason') or '状态更新'
    if not queue_item_id or not new_status:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    # Preload item for permission checks
    item = (
        QueueItem.objects.select_related('queue', 'patient')
        .filter(id=queue_item_id)
        .first()
    )
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    user: User = request.user  # type: ignore[assignment]
    # Ensure admin has access to the item's group
    if user.group and item.queue.group and item.queue.group != user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    # Validate transition
    if not _can_transition(item.status, new_status):
        return Response({'detail': f'无法从 {item.status} 转换为 {new_status}'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        # Lock the item row
        locked_item = (
            QueueItem.objects.select_for_update().select_related('queue').get(id=item.id)
        )
        old_status = locked_item.status
        now = timezone.now()
        locked_item.status = new_status
        if new_status == '就诊中':
            locked_item.started_at = now
        if new_status == '已完成':
            locked_item.completed_at = now
        locked_item.save()
        QueueItemTransition.objects.create(
            item=locked_item,
            from_status=old_status,
            to_status=new_status,
            operator=user,
            reason=reason,
        )
        queue = locked_item.queue
        # If completed, automatically progress next waiting item
        if new_status == '已完成':
            waiting_items = queue.items.filter(status='等待中').order_by('created_at')
            if waiting_items.exists():
                next_item = waiting_items.first()
                next_item.status = '就诊中'
                next_item.started_at = now
                next_item.save()
                QueueItemTransition.objects.create(
                    item=next_item,
                    from_status='等待中',
                    to_status='就诊中',
                    operator=None,
                    reason='自动推进就诊',
                )
                queue.current_number = next_item.number
        # Recalculate waiting count
        queue.waiting_count = queue.items.filter(status='等待中').count()
        queue.save()
    return Response({'success': True, 'newStatus': new_status})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_item_set_priority(request):
    """Administrators set the priority of a queue item."""
    queue_item_id = request.data.get('id') or request.data.get('queueItemId')
    priority = request.data.get('priority')
    if not queue_item_id or not priority:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    item = QueueItem.objects.select_related('queue').filter(id=queue_item_id).first()
    if not item:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    user: User = request.user  # type: ignore[assignment]
    if user.group and item.queue.group and item.queue.group != user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    if priority not in dict(QueueItem.PRIORITY_CHOICES).keys():
        return Response({'detail': '无效的优先级'}, status=status.HTTP_400_BAD_REQUEST)
    item.priority = priority
    item.save()
    return Response({'success': True, 'newPriority': priority})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_list_all(request):
    """Return a list of queues with statistics for administrators."""
    user: User = request.user  # type: ignore[assignment]
    qs = Queue.objects.all()
    if user.group:
        qs = qs.filter(group=user.group)
    data: list[dict] = []
    for q in qs:
        active_items = q.items.filter(status__in=['等待中', '就诊中']).count()
        data.append({
            'id': q.id,
            'name': q.name,
            'departmentId': q.department,
            'currentNumber': q.current_number,
            'waitingCount': q.waiting_count,
            'estimatedTime': q.estimated_time,
            'status': q.status,
            'itemCount': q.items.count(),
            'activeItems': active_items,
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_stats(request):
    """Return aggregate statistics for queues accessible to the admin."""
    user: User = request.user  # type: ignore[assignment]
    qs = Queue.objects.all()
    if user.group:
        qs = qs.filter(group=user.group)
    total_queues = qs.count()
    total_items = 0
    waiting_count = 0
    in_progress_count = 0
    completed_count = 0
    cancelled_count = 0
    urgent_count = 0
    high_count = 0
    for q in qs:
        items = q.items.all()
        total_items += items.count()
        waiting_count += items.filter(status='等待中').count()
        in_progress_count += items.filter(status='就诊中').count()
        completed_count += items.filter(status='已完成').count()
        cancelled_count += items.filter(status='已取消').count()
        urgent_count += items.filter(priority='urgent').count()
        high_count += items.filter(priority='high').count()
    return Response({
        'totalQueues': total_queues,
        'totalItems': total_items,
        'waitingCount': waiting_count,
        'inProgressCount': in_progress_count,
        'completedCount': completed_count,
        'cancelledCount': cancelled_count,
        'urgentCount': urgent_count,
        'highPriorityCount': high_count,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def admin_queue_broadcast(request):
    """Broadcast a message to one or more queues."""
    message = request.data.get('message')
    queue_ids = request.data.get('queueIds') or request.data.get('queue_ids')
    if not message:
        return Response({'detail': 'missing message'}, status=status.HTTP_400_BAD_REQUEST)
    user: User = request.user  # type: ignore[assignment]
    qs = Queue.objects.all()
    if user.group:
        qs = qs.filter(group=user.group)
    if queue_ids:
        if isinstance(queue_ids, str):
            queue_ids = [queue_ids]
        qs = qs.filter(id__in=queue_ids)
    total = qs.count()
    return Response({
        'success': True,
        'message': f'已向 {total} 个队列发送通知',
        'totalQueues': total,
        'broadcastTime': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'content': message,
    })