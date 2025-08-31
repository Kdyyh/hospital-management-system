from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from core.models import Group
from core.services.kpi import latest_kpi_for_group, latest_kpi_for_groups, format_kpi, format_kpi_with_group
from core.services.doctors import list_doctors

class Command(BaseCommand):
    help = "Warm and refresh API caches; broadcast WebSocket refresh event."

    def handle(self, *args, **options):
        now = timezone.now()
        keys_refreshed = []

        # KPI per group
        group_ids = list(Group.objects.values_list('id', flat=True))
        for gid in group_ids:
            kpi = latest_kpi_for_group(gid)
            payload = {'ok': True, 'data': (format_kpi(kpi) if kpi else None)}
            ck = f'kpi:group:{gid}'
            cache.set(ck, payload, 300)
            keys_refreshed.append(ck)

        # KPI all
        from core.models import GroupKPI
        kpis_latest = latest_kpi_for_groups(group_ids)
        kpis_latest = GroupKPI.objects.filter(id__in=[k.id for k in kpis_latest]).select_related('group')
        payload_all = {'ok': True, 'data': [format_kpi_with_group(k) for k in kpis_latest]}
        cache.set('kpi:all', payload_all, 300)
        keys_refreshed.append('kpi:all')

        # Doctors per group (base variants)
        for gid in group_ids:
            # all doctors
            data, total = list_doctors(gid)
            meta = {'groupId': gid}
            cache.set(f'doctors:g={gid}:q=:duty=0:p=None:ps=None', {'ok': True, 'meta': meta, 'data': data, 'pagination': {'total': total, 'page': 1, 'pageSize': total}}, 300)
            keys_refreshed.append(f'doctors:g={gid}:q=:duty=0:p=None:ps=None')
            # on duty only
            data_duty, total_duty = list_doctors(gid, on_duty_only=True)
            cache.set(f'doctors:g={gid}:q=:duty=1:p=None:ps=None', {'ok': True, 'meta': meta, 'data': data_duty, 'pagination': {'total': total_duty, 'page': 1, 'pageSize': total_duty}}, 300)
            keys_refreshed.append(f'doctors:g={gid}:q=:duty=1:p=None:ps=None')

        # Broadcast WebSocket message
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            event = {"type": "broadcast.refresh", "version": int(now.timestamp()), "ts": now.isoformat(), "keys": keys_refreshed[:50]}
            async_to_sync(channel_layer.group_send)("updates", event)

        self.stdout.write(self.style.SUCCESS(f"Refreshed {len(keys_refreshed)} keys at {now}"))
