from django.db import connections
from django.http import JsonResponse

def healthz(request):
    try:
        with connections['default'].cursor() as c:
            c.execute('SELECT 1')
            row = c.fetchone()
        return JsonResponse({'ok': True, 'db': bool(row and row[0]==1)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
