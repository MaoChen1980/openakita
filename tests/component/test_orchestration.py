"""L2 Component Tests: Orchestration registry and handoff."""

import pytest
from unittest.mock import MagicMock

from openakita.orchestration.registry import AgentRegistry
from openakita.orchestration.messages import (
    AgentInfo,
    AgentStatus,
    AgentType,
)
from openakita.orchestration.handoff import (
    HandoffAgent,
    HandoffTarget,
    HandoffOrchestrator,
    HandoffEvent,
)


class TestAgentRegistry:
    @pytest.fixture
    def registry(self):
        return AgentRegistry(heartbeat_timeout=30)

    def test_empty_registry(self, registry):
        assert registry.count() == 0
        assert registry.list_all() == []

    def test_register_agent(self, registry):
        info = AgentInfo(agent_id="w1", agent_type="worker", process_id=100)
        result = registry.register(info)
        assert result is True
        assert registry.count() == 1

    def test_get_registered(self, registry):
        info = AgentInfo(agent_id="w2", agent_type="worker", process_id=200)
        registry.register(info)
        retrieved = registry.get("w2")
        assert retrieved is not None
        assert retrieved.agent_id == "w2"

    def test_unregister(self, registry):
        info = AgentInfo(agent_id="w3", agent_type="worker", process_id=300)
        registry.register(info)
        result = registry.unregister("w3")
        assert result is True
        assert registry.count() == 0

    def test_heartbeat(self, registry):
        info = AgentInfo(agent_id="w4", agent_type="worker", process_id=400)
        registry.register(info)
        result = registry.heartbeat("w4")
        assert result is True

    def test_set_agent_status(self, registry):
        info = AgentInfo(agent_id="w5", agent_type="worker", process_id=500)
        registry.register(info)
        result = registry.set_agent_status("w5", AgentStatus.BUSY)
        assert result is True

    def test_set_and_clear_task(self, registry):
        info = AgentInfo(agent_id="w6", agent_type="worker", process_id=600)
        registry.register(info)
        registry.set_agent_task("w6", "task-1", "Process data")
        agent = registry.get("w6")
        assert agent.current_task == "task-1"
        registry.clear_agent_task("w6", success=True)
        agent = registry.get("w6")
        assert agent.current_task is None

    def test_find_idle_agent(self, registry):
        info = AgentInfo(agent_id="w7", agent_type="worker", process_id=700)
        info.set_status(AgentStatus.IDLE)
        registry.register(info)
        found = registry.find_idle_agent()
        assert found is not None

    def test_count_by_status(self, registry):
        counts = registry.count_by_status()
        assert isinstance(counts, dict)

    def test_dashboard_data(self, registry):
        data = registry.get_dashboard_data()
        assert isinstance(data, dict)

    def test_cleanup_dead_agents(self, registry):
        removed = registry.cleanup_dead_agents(max_age_hours=0)
        assert isinstance(removed, int)


class TestHandoffAgent:
    def test_create_agent(self):
        agent = HandoffAgent(name="researcher", description="Research agent")
        assert agent.name == "researcher"
        assert agent.handoffs == []

    def test_add_handoff(self):
        a1 = HandoffAgent(name="coordinator", description="Coords")
        a2 = HandoffAgent(name="worker", description="Works")
        a1.add_handoff(a2, description="Delegate to worker")
        assert len(a1.handoffs) == 1

    def test_get_handoff_tools(self):
        a1 = HandoffAgent(name="coord", description="Coordinator")
        a2 = HandoffAgent(name="exec", description="Executor")
        a1.add_handoff(a2, description="Execute task")
        tools = a1.get_handoff_tools()
        assert isinstance(tools, list)
        assert len(tools) == 1


class TestHandoffOrchestrator:
    def test_create_orchestrator(self):
        a1 = HandoffAgent(name="main", description="Main agent")
        orch = HandoffOrchestrator(agents=[a1], entry_agent=a1)
        assert orch.current_agent.name == "main"

    def test_handoff_history(self):
        a1 = HandoffAgent(name="main", description="Main")
        orch = HandoffOrchestrator(agents=[a1], entry_agent=a1)
        assert orch.handoff_history == []

    def test_get_summary(self):
        a1 = HandoffAgent(name="main", description="Main")
        orch = HandoffOrchestrator(agents=[a1], entry_agent=a1)
        summary = orch.get_summary()
        assert isinstance(summary, dict)


class TestHandoffEvent:
    def test_create_event(self):
        e = HandoffEvent(from_agent="a1", to_agent="a2", message="Take over")
        assert e.from_agent == "a1"
        assert e.timestamp > 0
