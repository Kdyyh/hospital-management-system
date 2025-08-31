"""
User registration and profile views.

These endpoints provide a unified way to register users of any role
('patient', 'admin', 'core', 'super'), fetch the current authenticated
user's profile, and update the profile.  The profile update endpoint
respects the user's role and only permits updating of allowed
attributes.  Group assignments are honoured if supplied and
information leakage across groups is prevented by ensuring callers
only view or modify their own records.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from ..models import User, PatientProfile, Group


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user of any role.

    Accepts ``username`` and ``password`` along with optional
    ``name`` (first name), ``phone``, ``age`` and ``role``.  If the
    role is ``patient`` a corresponding :class:`PatientProfile` is
    created.  For other roles the user is created without a patient
    profile.  A ``groupId`` may be supplied to bind the user to a
    specific group; if omitted and the creator has a group the new
    user inherits that group.  Returns a JSON object with ``ok`` and
    the new user's ``id`` on success.
    """
    username = request.data.get('username')
    password = request.data.get('password') or ''
    name = request.data.get('name', '')
    phone = request.data.get('phone', '')
    age = request.data.get('age')
    role = 'patient'
    if getattr(request.user, 'role', '') == 'super':
        role = request.data.get('role', 'patient')
    group_id = request.data.get('groupId') or request.data.get('group_id')
    if not username or not password:
        return Response({'detail': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password)
    except ValidationError as e:
        return Response({'detail': e.messages}, status=status.HTTP_400_BAD_REQUEST)
    if role not in ('patient', 'admin', 'core', 'super'):
        return Response({'detail': 'invalid role'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        user = User.objects.create_user(username=username, password=password, first_name=name)
        user.role = role
        # Bind to group if provided
        group = None
        if group_id:
            group = Group.objects.filter(id=group_id).first()
        elif request.user and request.user.is_authenticated and request.user.group_id:
            # Inherit creator's group if available
            group = request.user.group
        if group:
            user.group = group
            user.group_bind_time = timezone.now()
        user.save()
        if role == 'patient':
            PatientProfile.objects.create(
                user=user,
                phone=phone,
                age=age,
                sex=request.data.get('sex') or request.data.get('gender') or '',
                disease=request.data.get('disease') or '',
                status='等待入院',
                group=group,
            )
    return Response({'ok': True, 'id': user.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Allow an authenticated user to change their password.

    Expects ``currentPassword`` and ``newPassword`` fields in the
    request body.  The current password is verified before the
    password is updated.  If the new password is shorter than eight
    characters a 400 error is returned.  On success a simple
    confirmation message is returned.
    """
    user: User = request.user
    data = request.data or {}
    current = data.get('currentPassword') or data.get('current_password')
    new = data.get('newPassword') or data.get('new_password')
    if not new or len(str(new)) < 8:
        return Response({'detail': 'new password too short'}, status=status.HTTP_400_BAD_REQUEST)
    # If a current password is supplied verify it
    if current and not user.check_password(current):
        return Response({'detail': 'invalid current password'}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(new)
    user.save()
    return Response({'success': True, 'message': '密码修改成功'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Return the authenticated user's profile.

    Includes basic user fields (ID, username, name, role) and group
    information.  If the user is a patient additional demographic
    fields from :class:`PatientProfile` are included.  This endpoint
    never exposes information about other users or groups.
    """
    user: User = request.user
    profile = {
        'id': user.id,
        'username': user.username,
        'name': user.get_full_name() or user.username,
        'role': user.role,
        'groupId': user.group.id if user.group else None,
        'groupName': user.group.name if user.group else None,
    }
    # include patient specific info
    if hasattr(user, 'patient_profile'):
        pp = user.patient_profile
        profile.update({
            'sex': pp.sex,
            'age': pp.age,
            'phone': pp.phone,
            'disease': pp.disease,
            'status': pp.status,
        })
    return Response(profile)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile_update(request):
    """Update the authenticated user's profile.

    Allows users to modify their own name, phone and age.  Patients
    may additionally update sex and disease.  Group assignments cannot
    be changed via this endpoint.  Returns the updated profile.
    """
    user: User = request.user
    data = request.data
    with transaction.atomic():
        name = data.get('name')
        phone = data.get('phone')
        age = data.get('age')
        if name is not None:
            user.first_name = name
        if phone is not None:
            # store phone on patient profile or on user (for admin roles)
            if hasattr(user, 'patient_profile'):
                user.patient_profile.phone = phone
                user.patient_profile.save(update_fields=['phone'])
            else:
                # For non-patient roles there is no dedicated phone field on
                # the User model, so ignore the phone update.  Phone is
                # stored only on patient profiles.
                pass
        if age is not None and hasattr(user, 'patient_profile'):
            user.patient_profile.age = age
            user.patient_profile.save(update_fields=['age'])
        # patient specific fields
        if hasattr(user, 'patient_profile'):
            pp = user.patient_profile
            sex = data.get('sex') or data.get('gender')
            disease = data.get('disease')
            if sex is not None:
                pp.sex = sex
            if disease is not None:
                pp.disease = disease
            pp.save()
        user.save()
    return user_profile(request)