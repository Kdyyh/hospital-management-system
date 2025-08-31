from django.http import JsonResponse

class DeprecatedInquiryMiddleware:
    """Return 410 for legacy Inquiry/PInquiry endpoints."""
    LEGACY_PREFIXES = ('/api/inquiry', '/api/pinquiry')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        if any(path.startswith(p) for p in self.LEGACY_PREFIXES):
            return JsonResponse(
                {'ok': False, 'error': {'code': 'deprecated', 'message': 'This API is deprecated. Use /api/consult/* instead.'}},
                status=410
            )
        return self.get_response(request)
