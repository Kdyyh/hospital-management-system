from typing import Optional, List, Dict
from django.db.models import Max
from core.models import Group, GroupKPI

def latest_kpi_for_group(group_id: int) -> Optional[GroupKPI]:
    return GroupKPI.objects.filter(group_id=group_id).order_by('-created_at').first()

def latest_kpi_for_groups(group_ids: list[int]) -> list[GroupKPI]:
    # 使用标准SQL兼容的方式获取每个组的最新KPI
    from django.db.models import Max
    # 先找到每个组的最大创建时间
    latest_times = GroupKPI.objects.filter(
        group_id__in=group_ids
    ).values('group_id').annotate(
        latest_created=Max('created_at')
    )
    
    # 然后获取这些最新时间的记录
    latest_kpis = []
    for item in latest_times:
        kpi = GroupKPI.objects.filter(
            group_id=item['group_id'],
            created_at=item['latest_created']
        ).first()
        if kpi:
            latest_kpis.append(kpi)
    
    return latest_kpis

def format_kpi(kpi: GroupKPI) -> dict:
    return {
        'groupId': kpi.group_id,
        'queueLen': kpi.queue_len,
        'avgWaitMin': kpi.avg_wait_min,
        'updatedAt': kpi.updated_at.isoformat(),
    }

def format_kpi_with_group(kpi: GroupKPI) -> dict:
    return {
        **format_kpi(kpi),
        'groupName': kpi.group.name if getattr(kpi, 'group', None) else None
    }
