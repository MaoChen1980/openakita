"""
消息通道模块

提供多平台 IM 集成能力:
- 统一消息类型
- 通道适配器
- 消息网关
- 媒体处理
"""

from .types import (
    MessageType,
    UnifiedMessage,
    MessageContent,
    MediaFile,
    OutgoingMessage,
)
from .base import ChannelAdapter
from .gateway import MessageGateway

__all__ = [
    # 类型
    "MessageType",
    "UnifiedMessage",
    "MessageContent",
    "MediaFile",
    "OutgoingMessage",
    # 适配器
    "ChannelAdapter",
    # 网关
    "MessageGateway",
]
