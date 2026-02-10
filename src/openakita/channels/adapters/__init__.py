"""
IM 通道适配器

各平台的具体实现:
- Telegram
- 飞书
- 企业微信（自建应用 / 智能机器人）
- 钉钉
- QQ
"""

from .dingtalk import DingTalkAdapter
from .feishu import FeishuAdapter
from .qq import QQAdapter
from .telegram import TelegramAdapter
from .wework import WeWorkAdapter
from .wework_bot import WeWorkBotAdapter

__all__ = [
    "TelegramAdapter",
    "FeishuAdapter",
    "WeWorkAdapter",
    "WeWorkBotAdapter",
    "DingTalkAdapter",
    "QQAdapter",
]
