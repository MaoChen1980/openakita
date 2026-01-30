"""
IM 通道适配器

各平台的具体实现:
- Telegram
- 飞书
- 企业微信
- 钉钉
- QQ
"""

from .telegram import TelegramAdapter
from .feishu import FeishuAdapter
from .wework import WeWorkAdapter
from .dingtalk import DingTalkAdapter
from .qq import QQAdapter

__all__ = [
    "TelegramAdapter",
    "FeishuAdapter",
    "WeWorkAdapter",
    "DingTalkAdapter",
    "QQAdapter",
]
