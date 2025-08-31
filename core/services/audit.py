from typing import Optional, Any, Dict
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import AuditEvent

User = get_user_model()

def log_action(*, user: Optional[User], action: str, object_type: Optional[str]=None, object_id: Optional[int]=None, detail: Optional[Dict[str, Any]]=None) -> AuditEvent:
    return AuditEvent.objects.create(
        user=user if isinstance(user, User) or getattr(user, 'id', None) else None,
        action=action,
        object_type=object_type, object_id=object_id,
        detail=detail or {},
    )
