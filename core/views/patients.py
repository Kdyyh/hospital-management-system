"""
Patient management views.

These endpoints allow administrative users to list and export patients
and for patients themselves to register into the system.  Access is
controlled via custom permission classes.
"""
from __future__ import annotations

import secrets
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from core.serializers.patient import PatientCreateSerializer, PatientListQuerySerializer
from core.services.patients import ensure_admin_bound_group_or_raise, create_patient
from rest_framework.exceptions import PermissionDenied
from core.models import PatientProfile

def _check_patient_object_scope(user, patient_id):
    obj = PatientProfile.objects.select_related('user','group').filter(id=patient_id).first()
    if not obj:
        from rest_framework.exceptions import NotFound
        raise NotFound('patient not found')
    if getattr(user, 'role', '') == 'super':
        return obj
    if not getattr(user, 'group_id', None) or obj.group_id != user.group_id:
        raise PermissionDenied('forbidden for this patient')
    return obj


from ..permissions import IsAdminRole
from ..models import User, PatientProfile, Group


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def list_patients(request):
    q = PatientListQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    dept_id = q.validated_data.get('deptId')
    qs = PatientProfile.objects.select_related('user', 'group')
    if getattr(request.user, 'role', '') == 'super':
        if dept_id:
            qs = qs.filter(group__id=dept_id)
    else:
        ensure_admin_bound_group_or_raise(request.user)
        qs = qs.filter(group=request.user.group)
    page = q.validated_data.get('page') or 1
    page_size = q.validated_data.get('pageSize') or 0
    if page_size:
        start = (page-1)*page_size
        end = start + page_size
        qs = qs.order_by('-id')[start:end]
    patients_data: list[dict] = []
    for patient in qs:
        patients_data.append({
            # Return the numeric user ID to match the front‑end mock
            'id': patient.user.id,
            'name': patient.user.get_full_name() or patient.user.username,
            'sex': patient.sex,
            'age': patient.age,
            'phone': patient.phone,
            'disease': patient.disease,
            'status': patient.status,
            'groupId': patient.group.id if patient.group else None,
            # 新增：病例描述、严重程度、预计住院天数
            'caseReport': patient.case_report,
            'severity': patient.severity,
            'estimatedDays': patient.estimated_days,
        })
    return Response(patients_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def export_patients(request):
    """Placeholder for exporting patient data.

    In this simplified implementation the export endpoint merely
    acknowledges the request.  In a full implementation you could
    generate a CSV or Excel file and return a download link.
    """
    return Response(True)


# 新增：更新患者信息
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def update_patient(request):
    """Update an existing patient's profile.

    Administrators may update demographic fields, disease, status,
    case_report, severity and estimated_days.  A ``groupId`` may be
    provided to reassign the patient to another department.
    """
    pid = request.data.get('id') or request.data.get('patientId')
    if not pid:
        return Response({'detail': 'missing id'}, status=status.HTTP_400_BAD_REQUEST)
    profile = PatientProfile.objects.select_related('user').filter(user__id=pid).first()
    if not profile:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Update fields if provided
    for field, key in [
        ('sex', ['sex', 'gender']),
        ('age', ['age']),
        ('phone', ['phone']),
        ('disease', ['disease']),
        ('status', ['status']),
        ('case_report', ['case_report', 'caseReport']),
        ('severity', ['severity']),
        ('estimated_days', ['estimatedDays', 'estimated_days']),
    ]:
        value = None
        for k in key:
            if k in request.data:
                value = request.data[k]
                break
        if value is not None and value != '':
            # Convert estimated_days to int
            if field == 'estimated_days':
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = None
            setattr(profile, field, value)
    # Update group
    group_id = request.data.get('groupId') or request.data.get('deptId')
    if group_id:
        group = Group.objects.filter(id=group_id).first()
        profile.group = group
        if profile.user:
            profile.user.group = group
            profile.user.group_bind_time = timezone.now()
            profile.user.save()
    profile.save()
    return Response({'success': True})


# 新增：删除患者（标记为流失）
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def delete_patient(request):
    """Mark a patient as lost or remove them from the system.

    Setting the patient's status to '流失' indicates that they are no longer
    part of the active queue.  Administrators may choose to delete the
    underlying user record entirely by passing ``hard=true``.
    """
    pid = request.data.get('id') or request.data.get('patientId')
    if not pid:
        return Response({'detail': 'missing id'}, status=status.HTTP_400_BAD_REQUEST)
    profile = PatientProfile.objects.select_related('user').filter(user__id=pid).first()
    if not profile:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    hard = str(request.data.get('hard') or '').lower() == 'true'
    if hard:
        # Delete the user and profile
        user = profile.user
        profile.delete()
        if user:
            user.delete()
    else:
        profile.status = '流失'
        profile.save()
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_register(request):
    """Register a new patient.

    Accepts basic demographic information and an optional ``groupId``
    assignment.  A new user account is created with the role
    ``patient`` and a corresponding :class:`PatientProfile` is created.
    Returns the ID of the created patient.
    """
    name = request.data.get('name', '')
    sex = request.data.get('sex') or request.data.get('gender') or ''
    age = request.data.get('age')
    phone = request.data.get('phone') or ''
    disease = request.data.get('disease') or ''
    group_id = request.data.get('groupId')
    # 新增：读取病例描述、病情严重程度和预计住院天数
    # 前端可能传递camelCase或snake_case两种命名，这里统一兼容处理
    case_report = request.data.get('case_report') or request.data.get('caseReport') or ''
    severity = request.data.get('severity') or ''
    estimated_days = request.data.get('estimated_days') or request.data.get('estimatedDays')
    try:
        estimated_days_int = int(estimated_days) if estimated_days is not None and estimated_days != '' else None
    except (TypeError, ValueError):
        estimated_days_int = None

    with transaction.atomic():
        # Create the user.  Use a generated username if none provided
        username = f"patient{int(timezone.now().timestamp())}"
        user = User.objects.create_user(username=username, password=secrets.token_urlsafe(12), first_name=name)
        user.role = 'patient'
        user.save()
        group = None
        if group_id:
            group = Group.objects.filter(id=group_id).first()
            if group:
                user.group = group
                user.group_bind_time = timezone.now()
                user.save()
        # 创建患者档案，同时保存新增字段
        patient_profile = PatientProfile.objects.create(
            user=user,
            sex=sex,
            age=age,
            phone=phone,
            disease=disease,
            status='等待入院',
            group=group,
            case_report=case_report,
            severity=severity,
            estimated_days=estimated_days_int,
        )
    # Include group/department identifiers in the response for
    # compatibility with the front‑end mock specification.  If the
    # patient was bound to a group return its ID both as ``groupId``
    # and ``departmentId``.  Otherwise these values remain ``None``.
    resp = {
        'ok': True,
        'id': user.id,
        'groupId': group.id if group else None,
        'departmentId': group.id if group else None,
    }
    return Response(resp)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def register_patient(request):
    """Secure patient registration with validation and strong password policy."""
    data = PatientCreateSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    ensure_admin_bound_group_or_raise(request.user)
    user, profile, initial_password = create_patient(
        request.user,
        name=data.validated_data['name'],
        sex=data.validated_data['sex'],
        age=data.validated_data['age'],
        phone=data.validated_data.get('phone'),
        group_id=data.validated_data.get('groupId'),
        password=data.validated_data.get('password') or None,
    )
    return Response({'ok': True, 'id': profile.id, 'userId': user.id, 'initialPassword': initial_password}, status=201)
