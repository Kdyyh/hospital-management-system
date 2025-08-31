from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from core.serializers.consult import ConsultOpenSerializer, ConsultSendSerializer, ConsultListQuerySerializer, ConsultReadSerializer, ConsultHistoryQuerySerializer
from core.services.consult import open_consult, send_message, list_consults, list_history, mark_read
from core.models import Consultation

User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def consult_open(request):
    s = ConsultOpenSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        target = User.objects.get(id=s.validated_data['targetUserId'])
    except User.DoesNotExist:
        return Response({'ok': False, 'detail': '目标用户不存在'}, status=404)
    try:
        c = open_consult(request.user, target, s.validated_data.get('type'))
    except PermissionError as e:
        return Response({'ok': False, 'detail': str(e)}, status=403)
    return Response({'ok': True, 'consultId': c.id, 'groupId': c.group_id, 'doctorId': c.doctor_id, 'patientId': c.patient_id})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def consult_list(request):
    q = ConsultListQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    data, total = list_consults(
        request.user,
        status=q.validated_data.get('status'),
        q=q.validated_data.get('q'),
        dept_id=q.validated_data.get('deptId'),
        page=q.validated_data.get('page', 1),
        page_size=q.validated_data.get('pageSize', 20),
    )
    return Response({'ok': True, 'data': data, 'pagination': {'total': total, 'page': q.validated_data.get('page', 1), 'pageSize': q.validated_data.get('pageSize', 20)}})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def consult_send(request):
    s = ConsultSendSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        c = Consultation.objects.get(id=s.validated_data['consultId'])
    except Consultation.DoesNotExist:
        return Response({'ok': False, 'detail': '会话不存在'}, status=404)
    files = request.FILES.getlist('files') if hasattr(request.FILES, 'getlist') else []
    try:
        msg = send_message(c, request.user, s.validated_data.get('content',''), files=files)
    except PermissionError as e:
        return Response({'ok': False, 'detail': str(e)}, status=403)
    except ValueError as e:
        return Response({'ok': False, 'detail': str(e)}, status=400)
    return Response({'ok': True, 'messageId': msg.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def consult_read(request):
    s = ConsultReadSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        c = Consultation.objects.get(id=s.validated_data['consultId'])
    except Consultation.DoesNotExist:
        return Response({'ok': False, 'detail': '会话不存在'}, status=404)
    try:
        n = mark_read(request.user, c, s.validated_data.get('upToMessageId'))
    except PermissionError as e:
        return Response({'ok': False, 'detail': str(e)}, status=403)
    return Response({'ok': True, 'updated': n})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def consult_history(request):
    q = ConsultHistoryQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    try:
        c = Consultation.objects.get(id=q.validated_data['consultId'])
    except Consultation.DoesNotExist:
        return Response({'ok': False, 'detail': '会话不存在'}, status=404)
    try:
        items, total = list_history(request.user, c, page=q.validated_data.get('page', 1), page_size=q.validated_data.get('pageSize', 20))
    except PermissionError as e:
        return Response({'ok': False, 'detail': str(e)}, status=403)
    return Response({'ok': True, 'data': items, 'pagination': {'total': total, 'page': q.validated_data.get('page', 1), 'pageSize': q.validated_data.get('pageSize', 20)}})
