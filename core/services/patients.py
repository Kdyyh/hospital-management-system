import secrets
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import Group, PatientProfile

User = get_user_model()

def ensure_admin_bound_group_or_raise(user):
    if getattr(user, 'role', '') == 'super':
        return None
    if not getattr(user, 'group_id', None):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('admin without bound group cannot view patients')
    return user.group

def create_patient(current_user, *, name, sex, age, phone=None, group_id=None, password=None):
    # Decide target group within isolation rules
    if getattr(current_user, 'role', '') == 'super':
        target_group = Group.objects.filter(id=group_id).first() if group_id else None
    else:
        if not current_user.group_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('admin without bound group cannot create patients')
        # non-super can only create in their own group (ignore arbitrary group_id)
        target_group = current_user.group

    # Validate or generate password
    if password:
        try:
            validate_password(password)
        except ValidationError as e:
            from rest_framework.exceptions import ValidationError as DRFValidation
            raise DRFValidation({'password': e.messages})
    else:
        password = secrets.token_urlsafe(12)

    # Create user & profile
    username = f"patient{int(timezone.now().timestamp())}"
    user = User.objects.create_user(username=username, password=password, first_name=name)
    user.role = 'patient'
    if target_group:
        user.group = target_group
        user.group_bind_time = timezone.now()
    user.save()

    profile = PatientProfile.objects.create(
        user=user, sex=sex, age=age, phone=phone or '', status='等待入院', group=target_group
    )

    # Return both objects and initial password for admin auditing/notification
    return user, profile, password
