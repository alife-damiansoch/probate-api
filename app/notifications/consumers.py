from channels.generic.websocket import AsyncWebsocketConsumer
import json


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.groupname = 'broadcast'
        await self.channel_layer.group_add(
            self.groupname,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.groupname,
            self.channel_name
        )

    async def notification(self, event):
        # Prepare the response data
        response_data = {
            'type': event['type'],
            'message': event['message'],
            'recipient': event['recipient'],
            'notification_id': event['notification_id'],
            'application_id': event['application_id'],
            'seen': event['seen'],
            'country': event.get('country'),  # Include country in the payload
        }

        # Include 'changes' only if it exists in the event
        if 'changes' in event:
            response_data['changes'] = event['changes']

        # Print the event for debugging purposes
        print("Event:", event)
        print("Response data being sent:", response_data)

        # Send the response data back to the WebSocket
        await self.send(text_data=json.dumps(response_data))
