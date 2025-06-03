import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from notifications import consumers

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r'ws/notifications/', consumers.NotificationConsumer.as_asgi()),
        ])
    ),
})

# """
# ASGI config for app project.
#
# It exposes the ASGI callable as a module-level variable named ``application``.
#
# For more information on this file, see
# https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
# """
#
# import os
#
# from django.core.asgi import get_asgi_application
#
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
#
# application = get_asgi_application()
