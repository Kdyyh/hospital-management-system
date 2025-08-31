import json
from channels.generic.websocket import AsyncWebsocketConsumer

class UpdatesConsumer(AsyncWebsocketConsumer):
    GROUP = "updates"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()
        # optional: initial ping
        await self.send(json.dumps({"type": "welcome", "message": "connected"}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def broadcast_refresh(self, event):
        # event: {"type": "broadcast.refresh", "version": int, "ts": "...", "keys": [...]}
        await self.send(json.dumps(event))
