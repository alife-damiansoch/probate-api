import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# Setup Django before importing anything that uses models
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from notifications import consumers

# Get Django ASGI application for HTTP
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,  # This was missing!
    'websocket': AuthMiddlewareStack(
        URLRouter([
            re_path(r'ws/notifications/', consumers.NotificationConsumer.as_asgi()),
        ])
    ),
})
