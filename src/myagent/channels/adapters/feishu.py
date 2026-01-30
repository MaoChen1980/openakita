"""
飞书适配器

基于 lark-oapi 库实现:
- 事件订阅
- 卡片消息
- 文本/图片/文件收发
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from ..base import ChannelAdapter
from ..types import (
    UnifiedMessage,
    OutgoingMessage,
    MessageContent,
    MediaFile,
    MediaStatus,
    MessageType,
)

logger = logging.getLogger(__name__)

# 延迟导入
lark_oapi = None


def _import_lark():
    """延迟导入 lark-oapi 库"""
    global lark_oapi
    if lark_oapi is None:
        try:
            import lark_oapi as lark
            lark_oapi = lark
        except ImportError:
            raise ImportError(
                "lark-oapi not installed. "
                "Run: pip install lark-oapi"
            )


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    verification_token: Optional[str] = None
    encrypt_key: Optional[str] = None


class FeishuAdapter(ChannelAdapter):
    """
    飞书适配器
    
    支持:
    - 事件订阅（消息接收）
    - 文本/富文本消息
    - 图片/文件
    - 卡片消息
    """
    
    channel_name = "feishu"
    
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        verification_token: Optional[str] = None,
        encrypt_key: Optional[str] = None,
        media_dir: Optional[Path] = None,
    ):
        """
        Args:
            app_id: 飞书应用 App ID
            app_secret: 飞书应用 App Secret
            verification_token: 事件订阅验证 Token
            encrypt_key: 事件加密密钥
            media_dir: 媒体文件存储目录
        """
        super().__init__()
        
        self.config = FeishuConfig(
            app_id=app_id,
            app_secret=app_secret,
            verification_token=verification_token,
            encrypt_key=encrypt_key,
        )
        self.media_dir = Path(media_dir) if media_dir else Path("data/media/feishu")
        self.media_dir.mkdir(parents=True, exist_ok=True)
        
        self._client: Optional[Any] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
    
    async def start(self) -> None:
        """启动飞书客户端"""
        _import_lark()
        
        # 创建客户端
        self._client = lark_oapi.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .build()
        
        # 获取 access token
        await self._refresh_token()
        
        self._running = True
        logger.info("Feishu adapter started")
    
    async def stop(self) -> None:
        """停止飞书客户端"""
        self._running = False
        self._client = None
        logger.info("Feishu adapter stopped")
    
    async def _refresh_token(self) -> str:
        """刷新 access token"""
        import time
        
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        # 获取 tenant_access_token
        request = lark_oapi.api.auth.v3.InternalTenantAccessTokenRequest.builder() \
            .request_body(
                lark_oapi.api.auth.v3.InternalTenantAccessTokenRequestBody.builder()
                .app_id(self.config.app_id)
                .app_secret(self.config.app_secret)
                .build()
            ) \
            .build()
        
        response = self._client.auth.v3.tenant_access_token.internal(request)
        
        if not response.success():
            raise RuntimeError(f"Failed to get access token: {response.msg}")
        
        self._access_token = response.data.tenant_access_token
        self._token_expires_at = time.time() + response.data.expire - 60  # 提前 60 秒刷新
        
        return self._access_token
    
    def handle_event(self, body: dict, headers: dict) -> dict:
        """
        处理飞书事件回调
        
        用于 Webhook 模式，接收飞书推送的事件
        
        Args:
            body: 请求体
            headers: 请求头
        
        Returns:
            响应体
        """
        # URL 验证
        if "challenge" in body:
            return {"challenge": body["challenge"]}
        
        # 验证签名
        if self.config.verification_token:
            token = body.get("token")
            if token != self.config.verification_token:
                logger.warning("Invalid verification token")
                return {"error": "invalid token"}
        
        # 处理事件
        event_type = body.get("header", {}).get("event_type")
        event = body.get("event", {})
        
        if event_type == "im.message.receive_v1":
            # 收到消息
            asyncio.create_task(self._handle_message_event(event))
        
        return {"success": True}
    
    async def _handle_message_event(self, event: dict) -> None:
        """处理消息事件"""
        try:
            message = event.get("message", {})
            sender = event.get("sender", {})
            
            # 转换为统一消息格式
            unified = await self._convert_message(message, sender)
            
            # 记录日志
            self._log_message(unified)
            
            # 触发回调
            await self._emit_message(unified)
            
        except Exception as e:
            logger.error(f"Error handling message event: {e}")
    
    async def _convert_message(self, message: dict, sender: dict) -> UnifiedMessage:
        """将飞书消息转换为统一格式"""
        content = MessageContent()
        message_type = MessageType.TEXT
        
        msg_type = message.get("message_type")
        msg_content = json.loads(message.get("content", "{}"))
        
        if msg_type == "text":
            content.text = msg_content.get("text", "")
        
        elif msg_type == "image":
            image_key = msg_content.get("image_key")
            if image_key:
                media = MediaFile.create(
                    filename=f"{image_key}.png",
                    mime_type="image/png",
                    file_id=image_key,
                )
                content.images.append(media)
                message_type = MessageType.IMAGE
        
        elif msg_type == "audio":
            file_key = msg_content.get("file_key")
            if file_key:
                media = MediaFile.create(
                    filename=f"{file_key}.opus",
                    mime_type="audio/opus",
                    file_id=file_key,
                )
                media.duration = msg_content.get("duration", 0) / 1000  # 毫秒转秒
                content.voices.append(media)
                message_type = MessageType.VOICE
        
        elif msg_type == "file":
            file_key = msg_content.get("file_key")
            file_name = msg_content.get("file_name", "file")
            if file_key:
                media = MediaFile.create(
                    filename=file_name,
                    mime_type="application/octet-stream",
                    file_id=file_key,
                )
                content.files.append(media)
                message_type = MessageType.FILE
        
        elif msg_type == "post":
            # 富文本
            content.text = self._parse_post_content(msg_content)
            message_type = MessageType.TEXT
        
        # 确定聊天类型
        chat_type = message.get("chat_type", "p2p")
        if chat_type == "p2p":
            chat_type = "private"
        elif chat_type == "group":
            chat_type = "group"
        
        sender_id = sender.get("sender_id", {})
        user_id = sender_id.get("user_id") or sender_id.get("open_id", "")
        
        return UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=message.get("message_id", ""),
            user_id=f"fs_{user_id}",
            channel_user_id=user_id,
            chat_id=message.get("chat_id", ""),
            content=content,
            chat_type=chat_type,
            reply_to=message.get("root_id"),
            raw={"message": message, "sender": sender},
        )
    
    def _parse_post_content(self, post: dict) -> str:
        """解析富文本内容"""
        result = []
        
        title = post.get("title", "")
        if title:
            result.append(title)
        
        for content in post.get("content", []):
            for item in content:
                if item.get("tag") == "text":
                    result.append(item.get("text", ""))
                elif item.get("tag") == "a":
                    result.append(f"[{item.get('text', '')}]({item.get('href', '')})")
                elif item.get("tag") == "at":
                    result.append(f"@{item.get('user_name', '')}")
        
        return "\n".join(result)
    
    async def send_message(self, message: OutgoingMessage) -> str:
        """发送消息"""
        if not self._client:
            raise RuntimeError("Feishu client not started")
        
        await self._refresh_token()
        
        # 构建消息内容
        if message.content.text and not message.content.has_media:
            # 纯文本消息
            msg_type = "text"
            content = json.dumps({"text": message.content.text})
        elif message.content.images:
            # 图片消息
            # 需要先上传图片获取 image_key
            image = message.content.images[0]
            if image.local_path:
                image_key = await self._upload_image(image.local_path)
                msg_type = "image"
                content = json.dumps({"image_key": image_key})
            else:
                msg_type = "text"
                content = json.dumps({"text": message.content.text or "[图片]"})
        else:
            msg_type = "text"
            content = json.dumps({"text": message.content.text or ""})
        
        # 发送消息
        request = lark_oapi.api.im.v1.CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                lark_oapi.api.im.v1.CreateMessageRequestBody.builder()
                .receive_id(message.chat_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            ) \
            .build()
        
        response = self._client.im.v1.message.create(request)
        
        if not response.success():
            raise RuntimeError(f"Failed to send message: {response.msg}")
        
        return response.data.message_id
    
    async def _upload_image(self, path: str) -> str:
        """上传图片"""
        with open(path, "rb") as f:
            request = lark_oapi.api.im.v1.CreateImageRequest.builder() \
                .request_body(
                    lark_oapi.api.im.v1.CreateImageRequestBody.builder()
                    .image_type("message")
                    .image(f)
                    .build()
                ) \
                .build()
            
            response = self._client.im.v1.image.create(request)
            
            if not response.success():
                raise RuntimeError(f"Failed to upload image: {response.msg}")
            
            return response.data.image_key
    
    async def download_media(self, media: MediaFile) -> Path:
        """下载媒体文件"""
        if not self._client:
            raise RuntimeError("Feishu client not started")
        
        if media.local_path and Path(media.local_path).exists():
            return Path(media.local_path)
        
        if not media.file_id:
            raise ValueError("Media has no file_id")
        
        await self._refresh_token()
        
        # 根据类型选择下载接口
        if media.is_image:
            request = lark_oapi.api.im.v1.GetImageRequest.builder() \
                .image_key(media.file_id) \
                .build()
            
            response = self._client.im.v1.image.get(request)
        else:
            request = lark_oapi.api.im.v1.GetMessageResourceRequest.builder() \
                .message_id("") \
                .file_key(media.file_id) \
                .type("file") \
                .build()
            
            response = self._client.im.v1.message_resource.get(request)
        
        if not response.success():
            raise RuntimeError(f"Failed to download media: {response.msg}")
        
        # 保存文件
        local_path = self.media_dir / media.filename
        with open(local_path, "wb") as f:
            f.write(response.file.read())
        
        media.local_path = str(local_path)
        media.status = MediaStatus.READY
        
        logger.info(f"Downloaded media: {media.filename}")
        return local_path
    
    async def upload_media(self, path: Path, mime_type: str) -> MediaFile:
        """上传媒体文件"""
        if mime_type.startswith("image/"):
            image_key = await self._upload_image(str(path))
            media = MediaFile.create(
                filename=path.name,
                mime_type=mime_type,
                file_id=image_key,
            )
            media.status = MediaStatus.READY
            return media
        
        # 其他类型文件上传
        # 飞书需要先发送消息才能上传文件
        return MediaFile.create(
            filename=path.name,
            mime_type=mime_type,
        )
    
    async def send_card(
        self,
        chat_id: str,
        card: dict,
    ) -> str:
        """
        发送卡片消息
        
        Args:
            chat_id: 聊天 ID
            card: 卡片内容（飞书卡片 JSON）
        
        Returns:
            消息 ID
        """
        if not self._client:
            raise RuntimeError("Feishu client not started")
        
        await self._refresh_token()
        
        request = lark_oapi.api.im.v1.CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                lark_oapi.api.im.v1.CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .build()
            ) \
            .build()
        
        response = self._client.im.v1.message.create(request)
        
        if not response.success():
            raise RuntimeError(f"Failed to send card: {response.msg}")
        
        return response.data.message_id
    
    def build_simple_card(
        self,
        title: str,
        content: str,
        buttons: Optional[list[dict]] = None,
    ) -> dict:
        """
        构建简单卡片
        
        Args:
            title: 标题
            content: 内容
            buttons: 按钮列表 [{"text": "按钮文字", "value": "回调值"}]
        
        Returns:
            卡片 JSON
        """
        elements = [
            {
                "tag": "markdown",
                "content": content,
            }
        ]
        
        if buttons:
            actions = []
            for btn in buttons:
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": btn["text"]},
                    "type": "primary",
                    "value": {"action": btn.get("value", btn["text"])},
                })
            
            elements.append({
                "tag": "action",
                "actions": actions,
            })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": elements,
        }
