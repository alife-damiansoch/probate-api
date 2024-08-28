from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from notifications import consumers

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter([
            re_path(r'ws/notifications/', consumers.NotificationConsumer.as_asgi()),  # Websocket localhost route
           
        ])
    ),
})
