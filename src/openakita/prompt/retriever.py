"""
Prompt Retriever - 从 MEMORY.md 检索相关片段

复用现有的 MemoryManager 和 VectorStore 实现语义搜索。
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory import MemoryManager

logger = logging.getLogger(__name__)


def retrieve_memory(
    query: str,
    memory_manager: "MemoryManager",
    max_tokens: int = 400,
    max_items: int = 5,
    min_importance: float = 0.5,
) -> str:
    """
    从记忆系统检索与查询相关的片段

    复用 MemoryManager.get_injection_context() 的实现，
    但提供更精细的 token 控制。

    Args:
        query: 查询文本（通常是用户输入）
        memory_manager: MemoryManager 实例
        max_tokens: 最大 token 预算
        max_items: 最大返回条目数
        min_importance: 最小重要性阈值

    Returns:
        格式化的记忆上下文
    """
    lines = []

    # 1. 加载 MEMORY.md 核心记忆（始终包含，但限制长度）
    core_memory = _get_core_memory(memory_manager, max_chars=max_tokens * 2)  # 2 chars/token
    if core_memory:
        lines.append("## 核心记忆\n")
        lines.append(core_memory)

    # 2. 搜索相关记忆（向量搜索优先，回退关键词搜索）
    if query and query.strip():
        related, used_vector = _search_related_memories(
            query=query,
            memory_manager=memory_manager,
            max_items=max_items,
            min_importance=min_importance,
        )
        if related:
            search_type = "语义匹配" if used_vector else "关键词匹配"
            lines.append(f"\n## 相关记忆（{search_type}）\n")
            lines.append(related)

    # 3. 应用 token 限制
    result = "\n".join(lines)
    max_chars = max_tokens * 4  # 保守估计 4 chars/token

    if len(result) > max_chars:
        result = result[:max_chars]
        # 尝试在最后一个完整行处截断
        last_newline = result.rfind("\n")
        if last_newline > max_chars * 0.8:  # 保留至少 80%
            result = result[:last_newline]
        result += "\n...(记忆已截断)"

    return result


def _get_core_memory(memory_manager: "MemoryManager", max_chars: int = 800) -> str:
    """
    获取 MEMORY.md 核心记忆

    Args:
        memory_manager: MemoryManager 实例
        max_chars: 最大字符数

    Returns:
        核心记忆文本
    """
    memory_path = getattr(memory_manager, "memory_md_path", None)
    if not memory_path or not memory_path.exists():
        return ""

    try:
        content = memory_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""

        # 如果内容太长，优先保留最近的条目
        if len(content) > max_chars:
            lines = content.split("\n")
            result_lines = []
            current_len = 0

            # 从后往前添加（最近的条目在后面）
            for line in reversed(lines):
                if current_len + len(line) + 1 > max_chars:
                    break
                result_lines.insert(0, line)
                current_len += len(line) + 1

            return "\n".join(result_lines)

        return content
    except Exception as e:
        logger.warning(f"Failed to read MEMORY.md: {e}")
        return ""


def _search_related_memories(
    query: str,
    memory_manager: "MemoryManager",
    max_items: int = 5,
    min_importance: float = 0.5,
) -> tuple[str, bool]:
    """
    搜索相关记忆（向量搜索优先，回退关键词搜索）

    Args:
        query: 查询文本
        memory_manager: MemoryManager 实例
        max_items: 最大返回条目数
        min_importance: 最小重要性阈值

    Returns:
        (格式化的相关记忆, 是否使用了向量搜索)
    """
    vector_store = getattr(memory_manager, "vector_store", None)

    # 优先向量搜索
    if vector_store and getattr(vector_store, "enabled", False):
        try:
            results = vector_store.search(
                query=query,
                limit=max_items,
                min_importance=min_importance,
            )
            if results:
                memories = getattr(memory_manager, "_memories", {})
                lines = []
                for memory_id, _distance in results:
                    memory = memories.get(memory_id)
                    if memory:
                        content = getattr(memory, "content", str(memory))
                        lines.append(f"- {content}")
                if lines:
                    return "\n".join(lines), True
        except Exception as e:
            logger.warning(f"Vector memory search failed, falling back to keyword: {e}")

    # 回退：关键词搜索
    keyword_search = getattr(memory_manager, "_keyword_search", None)
    if keyword_search:
        try:
            results = keyword_search(query, max_items)
            if results:
                lines = [f"- {getattr(m, 'content', str(m))}" for m in results]
                return "\n".join(lines), False
        except Exception as e:
            logger.warning(f"Keyword memory search failed: {e}")

    return "", False


async def async_search_related_memories(
    query: str,
    memory_manager: "MemoryManager",
    max_items: int = 5,
    min_importance: float = 0.5,
) -> tuple[str, bool]:
    """
    异步版本的搜索相关记忆（向量搜索优先，回退关键词搜索）

    参数和返回值与 _search_related_memories() 完全相同。
    """
    vector_store = getattr(memory_manager, "vector_store", None)

    # 优先向量搜索
    if vector_store and getattr(vector_store, "enabled", False):
        try:
            results = await vector_store.async_search(
                query=query,
                limit=max_items,
                min_importance=min_importance,
            )
            if results:
                memories = getattr(memory_manager, "_memories", {})
                lines = []
                for memory_id, _distance in results:
                    memory = memories.get(memory_id)
                    if memory:
                        content = getattr(memory, "content", str(memory))
                        lines.append(f"- {content}")
                if lines:
                    return "\n".join(lines), True
        except Exception as e:
            logger.warning(f"Async vector memory search failed, falling back to keyword: {e}")

    # 回退：关键词搜索（同步，通过 to_thread 避免阻塞）
    keyword_search = getattr(memory_manager, "_keyword_search", None)
    if keyword_search:
        try:
            import asyncio
            results = await asyncio.to_thread(keyword_search, query, max_items)
            if results:
                lines = [f"- {getattr(m, 'content', str(m))}" for m in results]
                return "\n".join(lines), False
        except Exception as e:
            logger.warning(f"Async keyword memory search failed: {e}")

    return "", False


def retrieve_memory_simple(
    memory_md_path: Path,
    max_chars: int = 800,
) -> str:
    """
    简单的记忆检索（不使用向量搜索）

    直接读取 MEMORY.md 内容，适用于没有 MemoryManager 实例的场景。

    Args:
        memory_md_path: MEMORY.md 文件路径
        max_chars: 最大字符数

    Returns:
        记忆内容
    """
    if not memory_md_path.exists():
        return ""

    try:
        content = memory_md_path.read_text(encoding="utf-8").strip()
        if len(content) > max_chars:
            # 优先保留最近的条目
            lines = content.split("\n")
            result_lines = []
            current_len = 0

            for line in reversed(lines):
                if current_len + len(line) + 1 > max_chars:
                    break
                result_lines.insert(0, line)
                current_len += len(line) + 1

            return "\n".join(result_lines)

        return content
    except Exception as e:
        logger.warning(f"Failed to read {memory_md_path}: {e}")
        return ""
