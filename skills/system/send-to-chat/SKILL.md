---
name: send-to-chat
description: "[DEPRECATED] Do not use. Text is forwarded by gateway; attachments must be delivered via deliver_artifacts with receipts as proof."
system: true
handler: im_channel
tool-name: send_to_chat
category: IM Channel
disable-model-invocation: true
---

# Send to Chat（已弃用）

本技能保留仅用于**兼容与人工参考**，不应再被模型自动调用。

## 变更原因

- **文本消息**：助手的自然语言回复会由**网关直接转发**给用户，不需要、也不应该通过工具发送。
- **附件交付**（文件/图片/语音）：必须使用 `deliver_artifacts`，并以其回执（receipt）作为“已交付”的唯一证据。

## 替代用法（推荐）

### 发送文本

直接用正常回复文本输出即可（网关会转发）。

### 发送附件

调用 `deliver_artifacts`，显式提供 manifest：

```json
{
  "artifacts": [
    {"type": "image", "path": "data/temp/screenshot.png", "caption": "这是截图"}
  ]
}
```
