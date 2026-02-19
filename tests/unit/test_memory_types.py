"""L1 Unit Tests: Memory data models."""

import pytest
from datetime import datetime

from openakita.memory.types import Memory, MemoryPriority, MemoryType


class TestMemoryType:
    def test_all_types_exist(self):
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.SKILL.value == "skill"
        assert MemoryType.CONTEXT.value == "context"
        assert MemoryType.RULE.value == "rule"
        assert MemoryType.ERROR.value == "error"
        assert MemoryType.PERSONA_TRAIT.value == "persona_trait"


class TestMemoryPriority:
    def test_all_priorities_exist(self):
        assert MemoryPriority.TRANSIENT.value == "transient"
        assert MemoryPriority.SHORT_TERM.value == "short_term"
        assert MemoryPriority.LONG_TERM.value == "long_term"
        assert MemoryPriority.PERMANENT.value == "permanent"


class TestMemoryCreation:
    def test_default_values(self):
        m = Memory(content="test fact")
        assert m.type == MemoryType.FACT
        assert m.priority == MemoryPriority.SHORT_TERM
        assert m.content == "test fact"
        assert m.importance_score == 0.5
        assert m.access_count == 0
        assert isinstance(m.id, str)
        assert len(m.id) > 0

    def test_custom_values(self):
        m = Memory(
            content="User likes Python",
            type=MemoryType.PREFERENCE,
            priority=MemoryPriority.LONG_TERM,
            importance_score=0.9,
            tags=["programming", "preference"],
            source="conversation",
        )
        assert m.type == MemoryType.PREFERENCE
        assert m.priority == MemoryPriority.LONG_TERM
        assert m.importance_score == 0.9
        assert "programming" in m.tags
        assert m.source == "conversation"

    def test_timestamps_set(self):
        before = datetime.now()
        m = Memory(content="test")
        after = datetime.now()
        assert before <= m.created_at <= after
        assert before <= m.updated_at <= after

    def test_unique_ids(self):
        m1 = Memory(content="a")
        m2 = Memory(content="b")
        assert m1.id != m2.id

    def test_tags_default_empty(self):
        m = Memory(content="test")
        assert m.tags == []

    def test_tags_are_independent(self):
        m1 = Memory(content="a")
        m2 = Memory(content="b")
        m1.tags.append("tag1")
        assert "tag1" not in m2.tags
