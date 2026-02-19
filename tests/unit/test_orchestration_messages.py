"""L1 Unit Tests: Orchestration message types and serialization."""

import json
import pytest

from openakita.orchestration.messages import (
    AgentStatus,
    AgentType,
    MessageType,
    CommandType,
    EventType,
    AgentInfo,
    AgentMessage,
    TaskPayload,
    TaskResult,
    create_register_command,
    create_chat_request,
    create_chat_response,
)


class TestAgentInfo:
    def test_create_info(self):
        info = AgentInfo(agent_id="agent-1", agent_type="worker", process_id=1234)
        assert info.agent_id == "agent-1"
        assert info.tasks_completed == 0

    def test_serialize_roundtrip(self):
        info = AgentInfo(agent_id="a1", agent_type="master", process_id=100)
        d = info.to_dict()
        restored = AgentInfo.from_dict(d)
        assert restored.agent_id == "a1"
        assert restored.agent_type == "master"

    def test_update_heartbeat(self):
        info = AgentInfo(agent_id="a1", agent_type="worker", process_id=1)
        old_hb = info.last_heartbeat
        info.update_heartbeat()

    def test_set_and_clear_task(self):
        info = AgentInfo(agent_id="a1", agent_type="worker", process_id=1)
        info.set_task("task-1", "Do something")
        assert info.current_task == "task-1"
        info.clear_task(success=True)
        assert info.current_task is None
        assert info.tasks_completed == 1


class TestAgentMessage:
    def test_create_command(self):
        msg = AgentMessage.command(
            sender_id="master", target_id="worker-1",
            command_type=CommandType.ASSIGN_TASK,
            payload={"task": "process data"},
        )
        assert msg.sender_id == "master"
        assert msg.command_type == CommandType.ASSIGN_TASK.value

    def test_create_event(self):
        msg = AgentMessage.event(
            sender_id="worker-1",
            event_type=EventType.TASK_COMPLETED,
            payload={"task_id": "t1"},
        )
        assert msg.event_type == EventType.TASK_COMPLETED.value

    def test_json_roundtrip(self):
        msg = AgentMessage.command(
            sender_id="m", target_id="w",
            command_type=CommandType.GET_STATUS,
            payload={},
        )
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.sender_id == "m"
        assert restored.target_id == "w"

    def test_bytes_roundtrip(self):
        msg = AgentMessage.heartbeat(
            sender_id="w1",
            agent_info=AgentInfo(agent_id="w1", agent_type="worker", process_id=1),
        )
        data = msg.to_bytes()
        restored = AgentMessage.from_bytes(data)
        assert restored.sender_id == "w1"

    def test_response_message(self):
        msg = AgentMessage.response(
            sender_id="worker", target_id="master",
            correlation_id="corr-123",
            payload={"result": "done"},
        )
        assert msg.correlation_id == "corr-123"


class TestTaskPayload:
    def test_create_and_serialize(self):
        p = TaskPayload(task_id="t1", task_type="chat", description="Handle query", content="Hello")
        d = p.to_dict()
        restored = TaskPayload.from_dict(d)
        assert restored.task_id == "t1"
        assert restored.content == "Hello"


class TestTaskResult:
    def test_success(self):
        r = TaskResult(task_id="t1", success=True, result="Answer", iterations=3)
        d = r.to_dict()
        restored = TaskResult.from_dict(d)
        assert restored.success is True

    def test_failure(self):
        r = TaskResult(task_id="t2", success=False, error="Timeout")
        assert r.error == "Timeout"


class TestFactoryFunctions:
    def test_create_register_command(self):
        info = AgentInfo(agent_id="w1", agent_type="worker", process_id=1)
        msg = create_register_command(info)
        assert isinstance(msg, AgentMessage)

    def test_create_chat_request(self):
        msg = create_chat_request(
            sender_id="master", target_id="worker",
            session_id="s1", message="Hello",
        )
        assert isinstance(msg, AgentMessage)

    def test_create_chat_response(self):
        msg = create_chat_response(
            sender_id="worker", target_id="master",
            correlation_id="c1", response="Hi there",
        )
        assert isinstance(msg, AgentMessage)


class TestEnums:
    def test_agent_status_values(self):
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.BUSY.value == "busy"
        assert AgentStatus.DEAD.value == "dead"

    def test_command_types(self):
        assert CommandType.ASSIGN_TASK.value == "assign_task"
        assert CommandType.CANCEL_TASK.value == "cancel_task"

    def test_event_types(self):
        assert EventType.TASK_COMPLETED.value == "task_completed"
