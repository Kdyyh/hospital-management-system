"""
Management and patient inquiry endpoints.

This module exposes a unified interface for both the administrative
message center and the patient facing inquiry list.  Administrators
can view inquiries from their own group (if bound) or all inquiries
and can mark, reply to and resolve them.  Patients see only their
own inquiries.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Inquiry, InquiryReply, User
from ..permissions import IsAdminRole


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_inquiries(request):
    """List inquiries for the current user.

    Administrators see all inquiries or those belonging to their bound
    group.  Patients see only their own inquiries.  The returned
    structure differs slightly depending on the caller's role to match
    the front‑end expectations.
    """
    user: User = request.user  # type: ignore[assignment]
    if user.role in ('admin', 'core', 'super'):
        # Admin sees inquiries, optionally filtered by group binding
        qs = Inquiry.objects.select_related('user').prefetch_related('replies')
        if user.group:
            qs = qs.filter(group=user.group)
        messages: list[dict] = []
        for inquiry in qs:
            # Skip closed inquiries?  The mock includes open ones only
            from_user = inquiry.user
            replies_data: list[dict] = []
            for reply in inquiry.replies.all():
                replies_data.append({
                    'id': f'r{reply.id}',
                    'text': reply.text,
                    'time': reply.created_at.strftime('%Y-%m-%d %H:%M'),
                    'by': reply.by.username if reply.by else '',
                    'byName': (reply.by.get_full_name() or reply.by.username) if reply.by else '',
                })
            messages.append({
                'id': inquiry.id,
                'title': inquiry.title,
                'content': inquiry.content,
                'time': inquiry.created_at.strftime('%Y-%m-%d %H:%M'),
                'read': False,
                'tags': ['重要'] if inquiry.important else ['普通'],
                'type': 'patient_inquiry',
                'canReply': True,
                'assignedAdmin': user.username,
                'fromName': from_user.get_full_name() or from_user.username,
                'fromRole': from_user.role,
                'fromId': from_user.username,
                'replies': replies_data,
            })
        return Response(messages)
    else:
        # Patient sees only their inquiries
        qs = Inquiry.objects.filter(user=user).prefetch_related('replies')
        data: list[dict] = []
        for inquiry in qs:
            replies_data: list[dict] = []
            for reply in inquiry.replies.all():
                replies_data.append({
                    'id': f'r{reply.id}',
                    'text': reply.text,
                    'time': reply.created_at.strftime('%Y-%m-%d %H:%M'),
                    'by': reply.by.username if reply.by else '',
                    'byName': (reply.by.get_full_name() or reply.by.username) if reply.by else '',
                })
            data.append({
                'id': inquiry.id,
                'title': inquiry.title,
                'content': inquiry.content,
                'time': inquiry.created_at.strftime('%Y-%m-%d %H:%M'),
                'fromName': user.get_full_name() or user.username,
                'fromRole': user.role,
                'fromId': user.username,
                'status': inquiry.status,
                'important': inquiry.important,
                'replies': replies_data,
            })
        return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def inquiry_reply(request):
    """Reply to an inquiry.

    Only administrators may reply.  The body should include ``id``
    (inquiry ID) and ``text``.  If the admin is bound to a group the
    inquiry must belong to that group.
    """
    inquiry_id = request.data.get('id')
    text = request.data.get('text') or request.data.get('content')
    if not inquiry_id or not text:
        return Response({'detail': 'missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
    inquiry = Inquiry.objects.filter(id=inquiry_id).first()
    if not inquiry:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Check group binding
    if request.user.group and inquiry.group and inquiry.group != request.user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    InquiryReply.objects.create(inquiry=inquiry, by=request.user, text=text)
    return Response(True)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def inquiry_mark(request):
    """Toggle the important flag on an inquiry."""
    inquiry_id = request.data.get('id')
    inquiry = Inquiry.objects.filter(id=inquiry_id).first()
    if not inquiry:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Check group binding
    if request.user.group and inquiry.group and inquiry.group != request.user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    inquiry.important = not inquiry.important
    inquiry.save()
    return Response({'important': inquiry.important})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def inquiry_resolve(request):
    """Mark an inquiry as closed."""
    inquiry_id = request.data.get('id')
    inquiry = Inquiry.objects.filter(id=inquiry_id).first()
    if not inquiry:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Check group binding
    if request.user.group and inquiry.group and inquiry.group != request.user.group:
        return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
    inquiry.status = 'closed'
    inquiry.save()
    return Response(True)