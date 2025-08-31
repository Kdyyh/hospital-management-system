from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core.permissions import IsAdminRole
from core.models import Group, GroupKPI
from core.services.kpi import latest_kpi_for_group, latest_kpi_for_groups, format_kpi, format_kpi_with_group
from django.core.cache import cache

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_department_kpi(request):
    """患者：查看自己科室的当前排队KPI（带缓存，5分钟刷新）。"""
    user = request.user
    group_id = getattr(user, 'group_id', None)
    
    # super用户不需要绑定科室，可以访问所有科室数据
    if not group_id and getattr(user, 'role', '') != 'super':
        return Response({'ok': False, 'detail': '未绑定科室'}, status=403)
    
    # 对于super用户，如果没有绑定科室，返回第一个科室的KPI或所有科室
    if getattr(user, 'role', '') == 'super' and not group_id:
        # super用户未绑定科室，返回所有科室的KPI
        from core.models import Group
        groups = Group.objects.all()
        if not groups.exists():
            return Response({'ok': True, 'data': None})
        
        # 获取所有科室的最新KPI
        group_ids = list(groups.values_list('id', flat=True))
        kpis = latest_kpi_for_groups(group_ids)
        if not kpis:
            return Response({'ok': True, 'data': None})
        
        # 返回第一个科室的KPI（或者可以根据需要返回所有）
        kpi = kpis[0]
        payload = {'ok': True, 'data': format_kpi(kpi)}
        return Response(payload)
    
    ck = f'kpi:group:{group_id}'
    cached = cache.get(ck)
    if cached: return Response(cached)
    kpi = latest_kpi_for_group(group_id)
    if not kpi:
        payload = {'ok': True, 'data': None}
        cache.set(ck, payload, 300)
        return Response(payload)
    payload = {'ok': True, 'data': format_kpi(kpi)}
    cache.set(ck, payload, 300)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def department_kpi(request):
    """科室管理员/核心管理员：查看本科室KPI（带缓存，5分钟刷新）。"""
    user = request.user
    group_id = getattr(user, 'group_id', None)
    
    # super用户不需要绑定科室，可以访问所有科室数据
    if not group_id and getattr(user, 'role', '') != 'super':
        return Response({'ok': False, 'detail': '未绑定科室'}, status=403)
    
    # 对于super用户，如果没有绑定科室，返回第一个科室的KPI
    if getattr(user, 'role', '') == 'super' and not group_id:
        from core.models import Group
        groups = Group.objects.all()
        if not groups.exists():
            return Response({'ok': True, 'data': None})
        
        # 获取所有科室的最新KPI
        group_ids = list(groups.values_list('id', flat=True))
        kpis = latest_kpi_for_groups(group_ids)
        if not kpis:
            return Response({'ok': True, 'data': None})
        
        # 返回第一个科室的KPI
        kpi = kpis[0]
        payload = {'ok': True, 'data': format_kpi(kpi)}
        return Response(payload)
    
    ck = f'kpi:group:{group_id}'
    cached = cache.get(ck)
    if cached: return Response(cached)
    kpi = latest_kpi_for_group(group_id)
    if not kpi:
        payload = {'ok': True, 'data': None}
        cache.set(ck, payload, 300)
        return Response(payload)
    payload = {'ok': True, 'data': format_kpi(kpi)}
    cache.set(ck, payload, 300)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_departments_kpi(request):
    """super：查看全部科室KPI（带缓存，5分钟刷新）。"""
    if getattr(request.user, 'role', '') != 'super':
        return Response({'ok': False, 'detail': 'forbidden'}, status=403)
    ck = 'kpi:all'
    cached = cache.get(ck)
    if cached: return Response(cached)
    from core.models import Group
    qs = Group.objects.all().values_list('id', flat=True)
    kpis = latest_kpi_for_groups(list(qs))
    from core.models import GroupKPI
    kpis = GroupKPI.objects.filter(id__in=[k.id for k in kpis]).select_related('group')
    payload = {'ok': True, 'data': [format_kpi_with_group(k) for k in kpis]}
    cache.set(ck, payload, 300)
    return Response(payload)
