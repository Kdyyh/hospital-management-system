"""
Patient facing online inquiry endpoints.

Patients can create inquiries, list them, view details and receive
replies from medical staff.  Administrators can respond to these
inquiries.  The data model mirrors the simplified mock provided by
the front‑end.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import PInquiry, PInquiryReply, User
from ..permissions import IsAdminRole, IsPatientRole


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatientRole])
def list_patient_inquiries(request):
    """Return a summary list of the current patient's inquiries."""
    user: User = request.user  # type: ignore[assignment]
    qs = PInquiry.objects.filter(user=user).prefetch_related('replies')
    data: list[dict] = []
    for inquiry in qs:
        # Determine status – if there is a reply by an admin after the last patient message it's replied
        last_reply = inquiry.replies.order_by('-created_at').first()
        status_str = '待回复'
        if last_reply and last_reply.by and last_reply.by.role in ('admin', 'core', 'super'):
            status_str = '已回复'
        updated_at = last_reply.created_at if last_reply else inquiry.created_at
        data.append({
            'id': inquiry.id,
            'title': inquiry.title,
            'status': status_str,
            'updatedAt': updated_at.strftime('%Y-%m-%d %H:%M'),
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatientRole])
def create_patient_inquiry(request):
    """Create a new patient inquiry."""
    title = request.data.get('title')
    content = request.data.get('content')
    if not title or not content:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    # Generate an identifier
    next_index = PInquiry.objects.count() + 1
    inquiry_id = f'q{next_index}'
    PInquiry.objects.create(
        id=inquiry_id,
        user=request.user,
        title=title,
        content=content,
        group=request.user.group,
    )
    return Response({'ok': True, 'id': inquiry_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatientRole])
def detail_patient_inquiry(request):
    """Return details of a specific patient inquiry."""
    inquiry_id = request.query_params.get('id') or request.data.get('id')
    inquiry = PInquiry.objects.filter(id=inquiry_id, user=request.user).first()
    if not inquiry:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    replies_data: list[dict] = []
    for reply in inquiry.replies.all():
        replies_data.append({
            'id': f'r{reply.id}',
            'text': reply.text,
            'time': reply.created_at.strftime('%Y-%m-%d %H:%M'),
            'by': reply.by.username if reply.by else '',
            'byName': (reply.by.get_full_name() or reply.by.username) if reply.by else '',
        })
    return Response({
        'id': inquiry.id,
        'userId': request.user.username,
        'title': inquiry.title,
        'content': inquiry.content,
        'createdAt': inquiry.created_at.strftime('%Y-%m-%d %H:%M'),
        'replies': replies_data,
        'groupId': inquiry.group.id if inquiry.group else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reply_patient_inquiry(request):
    """Reply to a patient inquiry.

    Patients can respond to their own inquiries; administrators can
    respond to inquiries in their group.  The body expects ``id``
    (inquiry ID) and ``text``.
    """
    inquiry_id = request.data.get('id')
    text = request.data.get('text') or request.data.get('content')
    if not inquiry_id or not text:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    inquiry = PInquiry.objects.filter(id=inquiry_id).first()
    if not inquiry:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    user: User = request.user  # type: ignore[assignment]
    # Patient may only reply to their own inquiry
    if user.role == 'patient':
        if inquiry.user != user:
            return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    else:
        # Admin must share the same group
        if user.group and inquiry.group and inquiry.group != user.group:
            return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    # Note: field name is ``pinquiry`` on the model
    from ..models import PInquiryReply  # Local import to avoid circular import
    PInquiryReply.objects.create(pinquiry=inquiry, by=user, text=text)
    return Response(True)