import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async

from core.models import Consultation
from core.services.consult import check_consult_access, send_message


async def _ws_error(ws, code: int, message: str, *, close: bool = False):
    """
    统一的错误下发格式。
    App 代码：4xxx（客户端错误）、5xxx（服务端错误）
    """
    payload = {"type": "error", "code": code, "message": message}
    try:
        await ws.send(json.dumps(payload))
    finally:
        if close:
            await ws.close(code=code)


class ConsultChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 解析路径参数 consult_id
        try:
            self.consult_id = int(self.scope["url_route"]["kwargs"].get("consult_id"))
        except Exception:
            await self.close(code=4001)
            return

        user = self.scope.get("user") or AnonymousUser()

        # 校验会话是否存在
        try:
            consult = await sync_to_async(Consultation.objects.get)(id=self.consult_id)
        except Consultation.DoesNotExist:
            await self.close(code=4004)
            return

        # 访问控制：患者/医生/科室管理员/超管
        allowed = await sync_to_async(check_consult_access)(user, consult)
        if not allowed:
            await self.close(code=4003)
            return

        # 加入群组并接受连接
        self.group_name = f"consult.{self.consult_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        # 解析 JSON
        try:
            data = json.loads(text_data)
        except Exception:
            await _ws_error(self, 4000, "invalid_json")
            return

        if not isinstance(data, dict):
            await _ws_error(self, 4001, "invalid_payload")
            return

        if data.get("type") != "send":
            await _ws_error(self, 4002, "unsupported_type")
            return

        # 内容校验
        content = data.get("content", "")
        if not isinstance(content, str):
            await _ws_error(self, 4003, "invalid_content_type")
            return
        content = content.strip()
        if not content:
            await _ws_error(self, 4004, "empty_message")
            return
        if len(content) > 2000:
            await _ws_error(self, 4005, "message_too_long")
            return

        user = self.scope.get("user") or AnonymousUser()

        try:
            consult = await sync_to_async(
                Consultation.objects.select_related("doctor", "patient", "group").get
            )(id=self.consult_id)

            # 持久化消息；服务层负责权限二次校验与业务副作用（未读数、时间戳等）
            await sync_to_async(send_message)(consult, user, content, files=[])

            # 成功后可选择回显 ACK（若服务层已广播，这里不再重复广播）
            await self.send(json.dumps({"type": "ack", "ok": True}))
        except Consultation.DoesNotExist:
            await _ws_error(self, 4006, "consult_not_found", close=True)
        except PermissionError:
            await _ws_error(self, 4007, "forbidden", close=True)
        except Exception:
            # 避免泄露内部异常细节
            await _ws_error(self, 5000, "server_error")

    # 供 group_send 使用的事件处理器：
    # await channel_layer.group_send(self.group_name, {"type": "consult.message", "payload": {...}})
    async def consult_message(self, event):
        """
        接收 group_send 的消息事件并透传给前端。
        事件格式约定：
            {"type": "consult.message", "payload": {...}}
        """
        payload = event.get("payload", {})
        await self.send(json.dumps({"type": "message", **payload}))
