"""
企业微信适配器

基于企业微信 API 实现:
- 回调验证
- 消息加解密
- 文本/图片/文件收发
"""

import asyncio
import hashlib
import logging
import time
import xml.etree.ElementTree as ET
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
class WeWorkConfig:
    """企业微信配置"""

    corp_id: str
    agent_id: str
    secret: str
    token: str | None = None
    encoding_aes_key: str | None = None


class WeWorkAdapter(ChannelAdapter):
    """
    企业微信适配器

    支持:
    - 回调模式（接收消息）
    - 文本/图片/文件消息
    - Markdown 消息
    """

    channel_name = "wework"

    API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(
        self,
        corp_id: str,
        agent_id: str,
        secret: str,
        token: str | None = None,
        encoding_aes_key: str | None = None,
        media_dir: Path | None = None,
    ):
        """
        Args:
            corp_id: 企业 ID
            agent_id: 应用 AgentId
            secret: 应用 Secret
            token: 回调 Token
            encoding_aes_key: 回调加密密钥
            media_dir: 媒体文件存储目录
        """
        super().__init__()

        self.config = WeWorkConfig(
            corp_id=corp_id,
            agent_id=agent_id,
            secret=secret,
            token=token,
            encoding_aes_key=encoding_aes_key,
        )
        self.media_dir = Path(media_dir) if media_dir else Path("data/media/wework")
        self.media_dir.mkdir(parents=True, exist_ok=True)

        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._http_client: Any | None = None

    async def start(self) -> None:
        """启动企业微信客户端"""
        _import_httpx()

        self._http_client = httpx.AsyncClient()
        await self._refresh_token()

        self._running = True
        logger.info("WeWork adapter started")

    async def stop(self) -> None:
        """停止企业微信客户端"""
        self._running = False

        if self._http_client:
            await self._http_client.aclose()

        logger.info("WeWork adapter stopped")

    async def _refresh_token(self) -> str:
        """刷新 access token"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        url = f"{self.API_BASE}/gettoken"
        params = {
            "corpid": self.config.corp_id,
            "corpsecret": self.config.secret,
        }

        response = await self._http_client.get(url, params=params)
        data = response.json()

        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"Failed to get access token: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"] - 60

        return self._access_token

    def verify_callback(
        self,
        signature: str,
        timestamp: str,
        nonce: str,
        echostr: str,
    ) -> str:
        """
        验证回调 URL

        Returns:
            解密后的 echostr
        """
        # 简化实现，实际需要解密
        # 验证签名
        items = [self.config.token or "", timestamp, nonce]
        items.sort()
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()

        if sha1 != signature:
            raise ValueError("Invalid signature")

        # 解密 echostr（这里简化处理）
        return echostr

    def handle_callback(
        self,
        body: str,
        signature: str,
        timestamp: str,
        nonce: str,
    ) -> dict:
        """
        处理回调消息

        Args:
            body: XML 消息体
            signature: 签名
            timestamp: 时间戳
            nonce: 随机数

        Returns:
            响应
        """
        # 解析 XML（简化实现，实际需要解密）
        try:
            root = ET.fromstring(body)
            msg_type = root.find("MsgType").text

            if msg_type == "text":
                asyncio.create_task(self._handle_text_message(root))
            elif msg_type == "image":
                asyncio.create_task(self._handle_image_message(root))
            elif msg_type == "voice":
                asyncio.create_task(self._handle_voice_message(root))
            elif msg_type == "file":
                asyncio.create_task(self._handle_file_message(root))

        except Exception as e:
            logger.error(f"Error handling callback: {e}")

        return {"success": True}

    async def _handle_text_message(self, root: ET.Element) -> None:
        """处理文本消息"""
        content = MessageContent(text=root.find("Content").text)

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=root.find("MsgId").text,
            user_id=f"ww_{root.find('FromUserName').text}",
            channel_user_id=root.find("FromUserName").text,
            chat_id=root.find("FromUserName").text,  # 私聊用用户 ID
            content=content,
            chat_type="private",
            raw={"xml": ET.tostring(root, encoding="unicode")},
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def _handle_image_message(self, root: ET.Element) -> None:
        """处理图片消息"""
        media = MediaFile.create(
            filename=f"{root.find('MediaId').text}.jpg",
            mime_type="image/jpeg",
            file_id=root.find("MediaId").text,
            url=root.find("PicUrl").text,
        )

        content = MessageContent(images=[media])

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=root.find("MsgId").text,
            user_id=f"ww_{root.find('FromUserName').text}",
            channel_user_id=root.find("FromUserName").text,
            chat_id=root.find("FromUserName").text,
            content=content,
            chat_type="private",
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def _handle_voice_message(self, root: ET.Element) -> None:
        """处理语音消息"""
        media = MediaFile.create(
            filename=f"{root.find('MediaId').text}.amr",
            mime_type="audio/amr",
            file_id=root.find("MediaId").text,
        )

        content = MessageContent(voices=[media])

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=root.find("MsgId").text,
            user_id=f"ww_{root.find('FromUserName').text}",
            channel_user_id=root.find("FromUserName").text,
            chat_id=root.find("FromUserName").text,
            content=content,
            chat_type="private",
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def _handle_file_message(self, root: ET.Element) -> None:
        """处理文件消息"""
        media = MediaFile.create(
            filename=root.find("FileName").text,
            mime_type="application/octet-stream",
            file_id=root.find("MediaId").text,
        )

        content = MessageContent(files=[media])

        unified = UnifiedMessage.create(
            channel=self.channel_name,
            channel_message_id=root.find("MsgId").text,
            user_id=f"ww_{root.find('FromUserName').text}",
            channel_user_id=root.find("FromUserName").text,
            chat_id=root.find("FromUserName").text,
            content=content,
            chat_type="private",
        )

        self._log_message(unified)
        await self._emit_message(unified)

    async def send_message(self, message: OutgoingMessage) -> str:
        """发送消息"""
        await self._refresh_token()

        url = f"{self.API_BASE}/message/send"
        params = {"access_token": self._access_token}

        # 构建消息体
        data = {
            "touser": message.chat_id,
            "agentid": self.config.agent_id,
        }

        if message.content.text and not message.content.has_media:
            # 文本消息
            data["msgtype"] = "text"
            data["text"] = {"content": message.content.text}
        elif message.content.images:
            # 图片消息
            image = message.content.images[0]
            if image.file_id:
                data["msgtype"] = "image"
                data["image"] = {"media_id": image.file_id}
            elif image.local_path:
                # 先上传
                media_id = await self._upload_media(image.local_path, "image")
                data["msgtype"] = "image"
                data["image"] = {"media_id": media_id}
        elif message.content.files:
            # 文件消息
            file = message.content.files[0]
            if file.file_id:
                data["msgtype"] = "file"
                data["file"] = {"media_id": file.file_id}
            elif file.local_path:
                media_id = await self._upload_media(file.local_path, "file")
                data["msgtype"] = "file"
                data["file"] = {"media_id": media_id}
        else:
            data["msgtype"] = "text"
            data["text"] = {"content": message.content.text or ""}

        response = await self._http_client.post(url, params=params, json=data)
        result = response.json()

        if result.get("errcode", 0) != 0:
            raise RuntimeError(f"Failed to send message: {result.get('errmsg')}")

        return result.get("msgid", "")

    async def send_markdown(
        self,
        user_id: str,
        content: str,
    ) -> str:
        """
        发送 Markdown 消息

        Args:
            user_id: 用户 ID
            content: Markdown 内容

        Returns:
            消息 ID
        """
        await self._refresh_token()

        url = f"{self.API_BASE}/message/send"
        params = {"access_token": self._access_token}

        data = {
            "touser": user_id,
            "agentid": self.config.agent_id,
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

        response = await self._http_client.post(url, params=params, json=data)
        result = response.json()

        if result.get("errcode", 0) != 0:
            raise RuntimeError(f"Failed to send markdown: {result.get('errmsg')}")

        return result.get("msgid", "")

    async def _upload_media(self, path: str, media_type: str) -> str:
        """上传媒体文件"""
        await self._refresh_token()

        url = f"{self.API_BASE}/media/upload"
        params = {
            "access_token": self._access_token,
            "type": media_type,
        }

        with open(path, "rb") as f:
            files = {"media": f}
            response = await self._http_client.post(url, params=params, files=files)

        result = response.json()

        if result.get("errcode", 0) != 0:
            raise RuntimeError(f"Failed to upload media: {result.get('errmsg')}")

        return result["media_id"]

    async def download_media(self, media: MediaFile) -> Path:
        """下载媒体文件"""
        if media.local_path and Path(media.local_path).exists():
            return Path(media.local_path)

        # 优先使用 URL
        if media.url:
            response = await self._http_client.get(media.url)
        elif media.file_id:
            await self._refresh_token()
            url = f"{self.API_BASE}/media/get"
            params = {
                "access_token": self._access_token,
                "media_id": media.file_id,
            }
            response = await self._http_client.get(url, params=params)
        else:
            raise ValueError("Media has no url or file_id")

        # 保存文件
        local_path = self.media_dir / media.filename
        with open(local_path, "wb") as f:
            f.write(response.content)

        media.local_path = str(local_path)
        media.status = MediaStatus.READY

        logger.info(f"Downloaded media: {media.filename}")
        return local_path

    async def upload_media(self, path: Path, mime_type: str) -> MediaFile:
        """上传媒体文件"""
        media_type = "image" if mime_type.startswith("image/") else "file"
        media_id = await self._upload_media(str(path), media_type)

        return MediaFile.create(
            filename=path.name,
            mime_type=mime_type,
            file_id=media_id,
        )
