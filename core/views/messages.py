"""
General and patient messages endpoints.

These endpoints provide a simplified simulation of the messaging
functionality present in the front‑end mock.  In a real application
this would be backed by a message model or service.
"""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import User


def _get_mock_messages(role: str) -> list[dict]:
    """Return a static list of message structures for the given role."""
    if role == 'patient':
        return [
            {
                'id': 'pm_101',
                'title': '就诊提醒',
                'content': '您明日 09:30 的复诊已预约，请提前10分钟到达。',
                'time': '2025-08-19 09:00',
                'read': False,
                'tags': ['预约', '提醒'],
                'type': 'system',
                'canReply': False,
            },
            {
                'id': 'pm_102',
                'title': '化验结果已出',
                'content': '常规血检结果已回传，医生将尽快反馈。',
                'time': '2025-08-18 18:40',
                'read': True,
                'type': 'system',
                'canReply': False,
            },
        ]
    # admin/core/super messages
    return [
        {
            'id': 'am_201',
            'title': '排班变更',
            'content': '周四上午门诊调整为李主任坐诊，请确认。',
            'time': '2025-08-19 08:10',
            'read': False,
            'tags': ['排班'],
            'type': 'system',
            'canReply': False,
            'fromName': '系统管理员',
            'fromRole': 'system',
            'fromId': 'sys_001',
        },
    ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messages(request):
    """Return messages for the current user based on their role."""
    user: User = request.user  # type: ignore[assignment]
    role = user.role if user.role in ['patient', 'admin', 'core', 'super'] else 'patient'
    msgs = _get_mock_messages(role)
    return Response(msgs)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_messages(request):
    """Return patient messages only (alias for messages)."""
    return Response(_get_mock_messages('patient'))