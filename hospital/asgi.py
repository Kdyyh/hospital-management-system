"""
ASGI config for hospital project.

Wires both HTTP (Django) and WebSocket (Channels).
Order matters: configure Django before importing any Django-dependent modules.
"""
import os

# 1) Configure settings before any Django import
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital.settings")

# 2) Ensure Django is fully set up (so models/auth work during imports)
import django  # noqa: E402
django.setup()  # noqa: E402

# 3) Now import ASGI/Channels components and app consumers
from django.core.asgi import get_asgi_application  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from django.urls import path  # noqa: E402

from core.realtime.consumers import UpdatesConsumer  # noqa: E402
from core.realtime.chat_consumers import ConsultChatConsumer  # noqa: E402

# HTTP app (Django)
django_asgi_app = get_asgi_application()

# WS routes
websocket_urlpatterns = [
    path("ws/updates/", UpdatesConsumer.as_asgi()),
    path("ws/consult/<int:consult_id>/", ConsultChatConsumer.as_asgi()),
]

# ASGI entrypoint
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
