from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from core.models import Group, GroupMember, DoctorShift
from django.core.cache import cache
from core.services.doctors import list_doctors

User = get_user_model()

def list_doctors(group_id: int, *, q: str|None=None, on_duty_only: bool=False, now=None, page:int|None=None, page_size:int|None=None):
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_department_doctors(request):
    """Return doctor list for the current user's department.
    Query params:
      - q: optional search (name/username contains)
      - onDutyOnly: 1|0  (only show doctors with current active shift)
      - page, pageSize: pagination (optional)
      - deptId: super only
    """
    group_id = getattr(request.user, 'group_id', None)
    if getattr(request.user, 'role', '') == 'super':
        dept = request.query_params.get('deptId')
        if dept:
            try:
                group_id = int(dept)
            except ValueError:
                return Response({'ok': False, 'detail': 'deptId 参数不合法'}, status=400)
    if not group_id:
        return Response({'ok': False, 'detail': '未绑定科室'}, status=403)

    q = (request.query_params.get('q') or '').strip() or None
    on_duty_only = (request.query_params.get('onDutyOnly') or '0') in ['1','true','True']
    try:
        page = int(request.query_params.get('page')) if request.query_params.get('page') else None
        page_size = int(request.query_params.get('pageSize')) if request.query_params.get('pageSize') else None
    except ValueError:
        return Response({'ok': False, 'detail': '分页参数不合法'}, status=400)

    cache_key = f"doctors:g={group_id}:q={q or ''}:duty={int(on_duty_only)}:p={page}:ps={page_size}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    doctors, total = list_doctors(group_id, q=q, on_duty_only=on_duty_only, page=page, page_size=page_size)
    try:
        g = Group.objects.get(id=group_id)
        meta = {'groupId': g.id, 'groupName': g.name, 'specialties': g.specialties}
    except Group.DoesNotExist:
        meta = {'groupId': group_id}

    payload = {'ok': True, 'meta': meta, 'data': doctors, 'pagination': {'total': total, 'page': page or 1, 'pageSize': page_size or total}}
    cache.set(cache_key, payload, 300)  # 60s cache
    return Response(payload)
