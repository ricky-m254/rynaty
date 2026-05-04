"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from config.runtime_bootstrap import ensure_pkg_resources_compat
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
ensure_pkg_resources_compat()

django_asgi_application = get_asgi_application()

from communication.realtime import communication_websocket_application


async def application(scope, receive, send):
    if scope["type"] == "websocket" and str(scope.get("path") or "").startswith("/ws/communication/"):
        await communication_websocket_application(scope, receive, send)
        return
    await django_asgi_application(scope, receive, send)
