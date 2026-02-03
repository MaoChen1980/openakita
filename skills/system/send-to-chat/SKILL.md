---
name: send-to-chat
description: Send messages/files to current IM chat (only available in IM session). When you need to send text responses, screenshots/images after desktop_screenshot, or voice/documents to user. Use file_path for files.
system: true
handler: im_channel
tool-name: send_to_chat
category: IM Channel
---

# Send to Chat

发送消息到当前 IM 聊天。

## Availability

**仅在 IM 会话中可用**（如 Telegram、飞书等）。

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| text | string | 否 | 要发送的文本消息 |
| file_path | string | 否 | 要发送的文件路径（图片、文档等） |
| voice_path | string | 否 | 要发送的语音文件路径 |
| caption | string | 否 | 文件的说明文字 |

至少提供 `text`、`file_path` 或 `voice_path` 其中之一。

## Examples

**发送文本消息**:
```json
{"text": "任务完成！"}
```

**发送截图**:
```json
{"file_path": "C:/Users/.../screenshot.png"}
```

**发送带说明的文件**:
```json
{
  "file_path": "report.pdf",
  "caption": "这是今天的报告"
}
```

## Workflow

1. 使用 `desktop_screenshot` 或 `browser_screenshot` 截图
2. 获取返回的 `file_path`
3. 调用 `send_to_chat(file_path=...)` 发送

## Related Skills

- `desktop-screenshot`: 截取桌面
- `browser-screenshot`: 截取浏览器页面
