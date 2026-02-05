"""
钉钉适配器

基于钉钉开放平台 API 实现:
- Stream 模式
- 机器人消息
- 文本/图片/文件收发
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..base import ChannelAdapter
from ..types import (
    MediaFile,
    MediaStatus,
    MessageContent,
    OutgoingMessage,
    UnifiedMessage,
)

logger = logging.getLogger(__name__)

# 延迟导入
httpx = None


def _import_httpx():
    global httpx
    if httpx is None:
        import httpx as hx

        httpx = hx


@dataclass
class DingTalkConfig:
    """钉钉配置"""

    app_key: str
    app_secret: str
    agent_id: str | None = None


class DingTalkAdapter(ChannelAdapter):
    """
    钉钉适配器

    支持:
    - 回调模式
    - Stream 模式
    - 文本/Markdown/卡片消息
    """

    channel_name = "dingtalk"

    API_BASE = "https://oapi.dingtalk.com"
    API_NEW = "https://api.dingtalk.com/v1.0"

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        agent_id: str | None = None,
        media_dir: Path | None = None,
    ):
        """
        Args:
            app_key: 应用 AppKey
            app_secret: 应用 AppSecret
            agent_id: 应用 AgentId（发送消息时需要）
            media_dir: 媒体文件存储目录
        """
        super().__init__()

        self.config = DingTalkConfig(
            app_key=app_key,
            app_secret=app_secret,
            agent_id=agent_id,
        )
        self.media_dir = Path(media_dir) if media_dir else Path("data/media/dingtalk")
        self.media_dir.mkdir(parents=True, exist_ok=True)

        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._http_client: Any | None = None

    async def start(self) -> None:
        """启动钉钉客户端"""
        _import_httpx()

        self._http_client = httpx.AsyncClient()
        await self._refresh_token()

        self._running = True
        logger.info("DingTalk adapter started")

    async def stop(self) -> None:
        """停止钉钉客户端"""
        self._running = False

        if self._http_client:
            await self._http_client.aclose()

        logger.info("DingTalk adapter stopped")

    async def _refresh_token(self) -> str:
        """刷新 access token"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        url = f"{self.API_BASE}/gettoken"
        params = {
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }

        response = await self._http_client.get(url, params=params)
        data = response.json()

        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"Failed to get access token: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"] - 60

        return self._access_token

    def verify_signature(
        self,
        timestamp: str,
        sign: str,
    ) -> bool:
        """
        验证回调签名

        Args:
            timestamp: 时间戳
            sign: 签名

        Returns:
            是否有效
        """
        string_to_sign = f"{timestamp}\n{self.config.app_secret}"
        hmac_code = hmac.new(
            self.config.app_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256,
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode()

        return sign == expected_sign

    def handle_callback(self, body: dict) -> dict:
        """
        处理回调消息

        Args:
            body: 回调消息体

        Returns:
            响应
        """
        try:
            # 获取消息类型
            msg_type = body.get("msgtype")

            if msg_type == "text":
                asyncio.create_task(self._handle_text_message(body))
            elif msg_type == "picture":
                asyncio.create_task(self._handle_image_message(body))
            elif msg_type == "file":
                asyncio.create_task(self._handle_file_message(body))

        except Exception as e:
            logger.error(f"Error handling callback: {e}")

        return {"msgtype": "empty"}

    async def _handle_text_message(self, body: dict) -> None:
        """处理文本消息"""
        text_content = body.get("text", {})
        content = MessageContent(text=text_content.get("content", ""))

        sender_id = body.get("senderStaffId") or body.get("senderId", "")
        conversation_id = body.get("conversationId", "")

        # 判断是否群聊
        chat_type = "private"
        if body.get("conversationType") == "2":
            chat_type = "group"

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=body.get("msgId", ""),
            user_id=f"dd_{sender_id}",
            channel_user_id=sender_id,
            chat_id=conversation_id,
            content=content,
            chat_type=chat_type,
            raw=body,
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def _handle_image_message(self, body: dict) -> None:
        """处理图片消息"""
        picture = body.get("content", {}).get("pictureDownloadCode", "")

        media = MediaFile.create(
            filename=f"{picture}.jpg",
            mime_type="image/jpeg",
            file_id=picture,
        )

        content = MessageContent(images=[media])

        sender_id = body.get("senderStaffId") or body.get("senderId", "")
        conversation_id = body.get("conversationId", "")

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=body.get("msgId", ""),
            user_id=f"dd_{sender_id}",
            channel_user_id=sender_id,
            chat_id=conversation_id,
            content=content,
            chat_type="private",
            raw=body,
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def _handle_file_message(self, body: dict) -> None:
        """处理文件消息"""
        file_info = body.get("content", {})

        media = MediaFile.create(
            filename=file_info.get("fileName", "file"),
            mime_type="application/octet-stream",
            file_id=file_info.get("downloadCode", ""),
        )

        content = MessageContent(files=[media])

        sender_id = body.get("senderStaffId") or body.get("senderId", "")
        conversation_id = body.get("conversationId", "")

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=body.get("msgId", ""),
            user_id=f"dd_{sender_id}",
            channel_user_id=sender_id,
            chat_id=conversation_id,
            content=content,
            chat_type="private",
            raw=body,
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def send_message(self, message: OutgoingMessage) -> str:
        """发送消息"""
        await self._refresh_token()

        # 使用机器人单聊接口
        url = f"{self.API_NEW}/robot/oToMessages/batchSend"
        headers = {"x-acs-dingtalk-access-token": self._access_token}

        # 构建消息体
        msg_param = {}
        msg_key = "sampleText"

        if message.content.text and not message.content.has_media:
            msg_key = "sampleText"
            msg_param = {"content": message.content.text}
        elif message.content.images:
            msg_key = "sampleImageMsg"
            image = message.content.images[0]
            if image.url:
                msg_param = {"photoURL": image.url}
            else:
                # 需要先上传
                msg_key = "sampleText"
                msg_param = {"content": message.content.text or "[图片]"}
        else:
            msg_key = "sampleText"
            msg_param = {"content": message.content.text or ""}

        data = {
            "robotCode": self.config.app_key,
            "userIds": [message.chat_id],
            "msgKey": msg_key,
            "msgParam": json.dumps(msg_param),
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        if "processQueryKey" not in result:
            error = result.get("message", "Unknown error")
            raise RuntimeError(f"Failed to send message: {error}")

        return result["processQueryKey"]

    async def send_markdown(
        self,
        user_id: str,
        title: str,
        text: str,
    ) -> str:
        """
        发送 Markdown 消息

        Args:
            user_id: 用户 ID
            title: 标题
            text: Markdown 内容

        Returns:
            消息 ID
        """
        await self._refresh_token()

        url = f"{self.API_NEW}/robot/oToMessages/batchSend"
        headers = {"x-acs-dingtalk-access-token": self._access_token}

        data = {
            "robotCode": self.config.app_key,
            "userIds": [user_id],
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps(
                {
                    "title": title,
                    "text": text,
                }
            ),
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        return result.get("processQueryKey", "")

    async def send_action_card(
        self,
        user_id: str,
        title: str,
        text: str,
        single_title: str,
        single_url: str,
    ) -> str:
        """
        发送卡片消息

        Args:
            user_id: 用户 ID
            title: 标题
            text: 内容
            single_title: 按钮文字
            single_url: 按钮链接

        Returns:
            消息 ID
        """
        await self._refresh_token()

        url = f"{self.API_NEW}/robot/oToMessages/batchSend"
        headers = {"x-acs-dingtalk-access-token": self._access_token}

        data = {
            "robotCode": self.config.app_key,
            "userIds": [user_id],
            "msgKey": "sampleActionCard",
            "msgParam": json.dumps(
                {
                    "title": title,
                    "text": text,
                    "singleTitle": single_title,
                    "singleURL": single_url,
                }
            ),
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        return result.get("processQueryKey", "")

    async def download_media(self, media: MediaFile) -> Path:
        """下载媒体文件"""
        if media.local_path and Path(media.local_path).exists():
            return Path(media.local_path)

        if not media.file_id:
            raise ValueError("Media has no file_id")

        await self._refresh_token()

        # 获取下载链接
        url = f"{self.API_NEW}/robot/messageFiles/download"
        headers = {"x-acs-dingtalk-access-token": self._access_token}
        params = {"downloadCode": media.file_id, "robotCode": self.config.app_key}

        response = await self._http_client.get(url, headers=headers, params=params)
        result = response.json()

        download_url = result.get("downloadUrl")
        if not download_url:
            raise RuntimeError("Failed to get download URL")

        # 下载文件
        response = await self._http_client.get(download_url)

        local_path = self.media_dir / media.filename
        with open(local_path, "wb") as f:
            f.write(response.content)

        media.local_path = str(local_path)
        media.status = MediaStatus.READY

        logger.info(f"Downloaded media: {media.filename}")
        return local_path

    async def upload_media(self, path: Path, mime_type: str) -> MediaFile:
        """上传媒体文件"""
        # 钉钉需要通过特定接口上传
        # 这里简化处理
        return MediaFile.create(
            filename=path.name,
            mime_type=mime_type,
        )
