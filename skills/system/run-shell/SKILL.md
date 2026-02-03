---
name: run-shell
description: Execute shell commands for system operations, directory creation, and script execution. When you need to run system commands, execute scripts, install packages, or manage processes. Note - if commands fail consecutively, try different approaches.
system: true
handler: filesystem
tool-name: run_shell
category: File System
---

# Run Shell

执行 Shell 命令。

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| command | string | 是 | 要执行的 Shell 命令 |
| cwd | string | 否 | 工作目录（可选） |
| timeout | integer | 否 | 超时时间（秒），默认 60，范围 10-600 |

## Examples

**列出目录**:
```json
{"command": "ls -la"}
```

**安装依赖**:
```json
{"command": "pip install requests", "timeout": 300}
```

**在指定目录执行**:
```json
{"command": "npm install", "cwd": "/path/to/project"}
```

## Timeout Guidelines

- 简单命令: 30-60 秒
- 安装/下载: 300 秒
- 长时间任务: 根据需要设置更长时间

## Notes

- Windows 使用 PowerShell/cmd 命令
- Linux/Mac 使用 bash 命令
- 如果命令连续失败，请尝试不同的命令或方法
- 失败时可调用 `get_session_logs` 查看详细日志

## Related Skills

- `write-file`: 写入文件
- `read-file`: 读取文件
