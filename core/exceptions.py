from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response

def api_exception_handler(exc, context):
    resp = drf_exception_handler(exc, context)
    if resp is None:
        return Response({'ok': False, 'error': {'code': 'server_error', 'message': str(exc)}}, status=500)
    # normalize response
    detail = None
    if isinstance(resp.data, dict):
        detail = resp.data.get('detail') or resp.data
    else:
        detail = str(resp.data)
    return Response({'ok': False, 'error': {'code': 'api_error', 'message': detail}}, status=resp.status_code)
