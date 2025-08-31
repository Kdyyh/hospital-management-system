from typing import Optional, Tuple, List, Dict
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import GroupMember, DoctorShift

User = get_user_model()

def list_doctors(group_id: int, *, q: Optional[str]=None, on_duty_only: bool=False,
                 now=None, page: Optional[int]=None, page_size: Optional[int]=None) -> tuple[list[dict], int]:
    now = now or timezone.now()
    qs = User.objects.filter(group_id=group_id, role__in=['admin','core']).only('id','first_name','username','role','group_id')
    if q:
        qs = qs.filter(first_name__icontains=q) | qs.filter(username__icontains=q)
    if on_duty_only:
        qs = qs.filter(doctor_shifts__start_at__lte=now, doctor_shifts__end_at__gt=now).distinct()

    total = qs.count()
    if page and page_size:
        start = (page-1)*page_size
        end = start + page_size
        qs = qs.order_by('id')[start:end]

    member_roles = {gm.user_id: gm.role for gm in GroupMember.objects.filter(group_id=group_id, user_id__in=qs.values_list('id', flat=True))}
    data = [{
        'id': u.id,
        'name': (u.first_name or u.username),
        'role': u.role,
        'position': member_roles.get(u.id, 'member'),
        'groupId': u.group_id,
    } for u in qs]
    return data, total
