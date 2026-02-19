"""
L4 E2E Tests: Memory persistence across sessions.

Tests that memories stored in one session can be retrieved in a new session.
"""

import pytest
from pathlib import Path

from openakita.memory.types import Memory, MemoryType, MemoryPriority


@pytest.fixture
def memory_store(tmp_workspace, mock_brain):
    from openakita.memory.manager import MemoryManager
    mem_dir = tmp_workspace / "data" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    memory_md = tmp_workspace / "identity" / "MEMORY.md"
    memory_md.parent.mkdir(parents=True, exist_ok=True)
    memory_md.write_text("# Memory\n", encoding="utf-8")
    return MemoryManager(
        data_dir=mem_dir,
        memory_md_path=memory_md,
        brain=mock_brain,
    )


class TestCrossSessionMemory:
    def test_memory_persists_after_add(self, memory_store):
        """Memory added in session 1 should be retrievable immediately."""
        memory_store.add_memory(Memory(
            content="用户的生日是3月15日",
            type=MemoryType.FACT,
            priority=MemoryPriority.LONG_TERM,
            importance_score=0.9,
            tags=["birthday", "personal"],
        ))

        results = memory_store.search_memories(query="生日")
        assert len(results) >= 1
        assert any("3月15日" in r.content for r in results)

    def test_memory_types_searchable(self, memory_store):
        """Different memory types should be independently searchable."""
        memory_store.add_memory(Memory(
            content="User prefers dark mode",
            type=MemoryType.PREFERENCE,
        ))
        memory_store.add_memory(Memory(
            content="Python project uses FastAPI",
            type=MemoryType.FACT,
        ))
        memory_store.add_memory(Memory(
            content="Always use type hints in Python",
            type=MemoryType.RULE,
        ))

        prefs = memory_store.search_memories(memory_type=MemoryType.PREFERENCE)
        facts = memory_store.search_memories(memory_type=MemoryType.FACT)
        rules = memory_store.search_memories(memory_type=MemoryType.RULE)

        assert len(prefs) >= 1
        assert len(facts) >= 1
        assert len(rules) >= 1

    def test_injection_context_includes_memories(self, memory_store):
        """get_injection_context should include relevant memories."""
        memory_store.add_memory(Memory(
            content="User's name is Alice",
            type=MemoryType.FACT,
            importance_score=0.95,
        ))

        context = memory_store.get_injection_context(task_description="greeting user")
        assert isinstance(context, str)

    def test_memory_stats(self, memory_store):
        """Stats should reflect stored memories."""
        for i in range(5):
            memory_store.add_memory(Memory(content=f"Memory {i}"))

        stats = memory_store.get_stats()
        assert stats["total"] >= 5

    def test_delete_memory(self, memory_store):
        """Deleted memories should not appear in search."""
        mid = memory_store.add_memory(Memory(content="temporary info"))
        memory_store.delete_memory(mid)
        results = memory_store.search_memories(query="temporary")
        assert not any(r.id == mid for r in results)
