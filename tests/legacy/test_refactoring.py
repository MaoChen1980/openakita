"""
OpenAkita 架构重构功能自检测试

验证所有新模块和修改模块的基本功能：
1. Phase 1: 基础设施 (AgentState, Tracing, ToolError)
2. Phase 2: Agent 拆分 (所有子模块导入和基本功能)
3. Phase 3: 增强功能 (记忆存储, async 兼容性)
4. Phase 4: 高级功能 (Checkpoint, Handoff, 评估框架)
5. 集成测试: agent.py 委托, config, main 入口
"""

import asyncio
import copy
import json
import os
import sys
import tempfile
import time

# 确保项目根目录在 path 上
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

passed = 0
failed = 0
errors = []


def test(name):
    """测试装饰器"""
    def decorator(fn):
        global passed, failed
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
            errors.append((name, str(e)))
    return decorator


def async_test(name):
    """异步测试装饰器"""
    def decorator(fn):
        global passed, failed
        try:
            asyncio.get_event_loop().run_until_complete(fn())
            print(f"  ✅ {name}")
            passed += 1
        except RuntimeError:
            # 没有事件循环时创建新的
            try:
                asyncio.run(fn())
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1
                errors.append((name, str(e)))
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
            errors.append((name, str(e)))
    return decorator


# ==================== Phase 1: 基础设施 ====================
print("\n📦 Phase 1: 基础设施")


@test("AgentState 导入和状态机")
def _():
    from openakita.core.agent_state import AgentState, TaskState, TaskStatus

    state = AgentState()
    assert not state.initialized
    assert not state.running

    task = state.begin_task()
    assert task is not None
    assert task.status == TaskStatus.IDLE
    assert state.current_task is task

    # IDLE -> REASONING (直接跳过编译阶段，适用于外部已编译的场景)
    task.transition(TaskStatus.REASONING)
    assert task.status == TaskStatus.REASONING

    task.transition(TaskStatus.ACTING)
    assert task.status == TaskStatus.ACTING

    task.transition(TaskStatus.OBSERVING)
    assert task.status == TaskStatus.OBSERVING

    # OBSERVING -> REASONING (正常循环)
    task.transition(TaskStatus.REASONING)
    assert task.status == TaskStatus.REASONING

    # REASONING -> COMPLETED (最终答案)
    task.transition(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED

    # 测试 IDLE -> COMPILING -> REASONING 完整路径
    state.reset_task()
    task2 = state.begin_task()
    task2.transition(TaskStatus.COMPILING)
    assert task2.status == TaskStatus.COMPILING
    task2.transition(TaskStatus.REASONING)
    assert task2.status == TaskStatus.REASONING


@test("Tracing 框架基本功能")
def _():
    from openakita.tracing.tracer import AgentTracer, SpanType, SpanStatus, get_tracer, set_tracer

    tracer = AgentTracer(enabled=True)
    set_tracer(tracer)

    # 测试 context manager API
    with tracer.start_trace("test-session") as trace:
        with tracer.llm_span(model="test-model") as span:
            span.set_attribute("input_tokens", 100)
            span.set_attribute("output_tokens", 50)
        with tracer.tool_span(tool_name="read_file") as span:
            span.set_attribute("result_length", 200)

    assert trace.span_count == 2
    summary = trace.get_summary()
    assert summary["llm_calls"] == 1
    assert summary["tool_calls"] == 1
    assert summary["total_input_tokens"] == 100

    # 测试非 context manager API (begin_trace/end_trace)
    tracer.begin_trace("test-session-2", metadata={"task": "test"})
    tracer.end_trace(metadata={"result": "ok"})

    # 恢复为 disabled
    set_tracer(AgentTracer(enabled=False))


@test("Tracing Exporter")
def _():
    from openakita.tracing.exporter import FileExporter, ConsoleExporter, TraceExporter
    assert issubclass(FileExporter, TraceExporter)
    assert issubclass(ConsoleExporter, TraceExporter)


@test("ToolError 结构化错误")
def _():
    from openakita.tools.errors import ToolError, ErrorType, classify_error

    # 测试直接创建
    err = ToolError(
        error_type=ErrorType.TRANSIENT,
        tool_name="run_shell",
        message="连接超时",
        retry_suggestion="请重试",
    )
    assert err.error_type == ErrorType.TRANSIENT
    result = err.to_tool_result()
    assert "连接超时" in result
    assert "请重试" in result

    # 测试 classify_error
    timeout_err = classify_error(TimeoutError("timed out"), tool_name="web_search")
    assert timeout_err.error_type == ErrorType.TIMEOUT

    perm_err = classify_error(PermissionError("access denied"), tool_name="write_file")
    assert perm_err.error_type == ErrorType.PERMISSION

    file_err = classify_error(FileNotFoundError("not found"), tool_name="read_file")
    assert file_err.error_type == ErrorType.RESOURCE_NOT_FOUND


# ==================== Phase 2: Agent 拆分 ====================
print("\n🔧 Phase 2: Agent 子模块拆分")


@test("ToolExecutor 导入")
def _():
    from openakita.core.tool_executor import ToolExecutor
    assert ToolExecutor is not None


@test("ContextManager 基本功能")
def _():
    from openakita.core.context_manager import ContextManager

    cm = ContextManager(brain=None)
    # 测试 token 估算
    tokens = cm.estimate_tokens("Hello, world!")
    assert tokens > 0

    # 测试消息 token 估算
    msgs = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
    ]
    msg_tokens = cm.estimate_messages_tokens(msgs)
    assert msg_tokens > 0

    # 测试消息分组
    groups = cm.group_messages(msgs)
    assert len(groups) > 0


@test("ResponseHandler 导入")
def _():
    from openakita.core.response_handler import (
        ResponseHandler, clean_llm_response,
        strip_thinking_tags, strip_tool_simulation_text,
    )
    # 测试 clean_llm_response
    text = "<thinking>内部思考</thinking>最终答案"
    cleaned = strip_thinking_tags(text)
    assert "内部思考" not in cleaned
    assert "最终答案" in cleaned


@test("SkillManager 导入")
def _():
    from openakita.core.skill_manager import SkillManager
    assert SkillManager is not None


@test("PromptAssembler 导入")
def _():
    from openakita.core.prompt_assembler import PromptAssembler
    assert PromptAssembler is not None


@test("ReasoningEngine 和 Checkpoint")
def _():
    from openakita.core.reasoning_engine import (
        ReasoningEngine, Decision, DecisionType, Checkpoint,
    )
    assert ReasoningEngine is not None
    assert Checkpoint is not None

    # 测试 Decision 数据类
    d = Decision(type=DecisionType.FINAL_ANSWER, text_content="测试完成")
    assert d.type == DecisionType.FINAL_ANSWER
    assert d.text_content == "测试完成"

    # 测试 Checkpoint 数据类
    cp = Checkpoint(
        id="test-cp",
        messages_snapshot=[{"role": "user", "content": "test"}],
        state_snapshot={"iteration": 1},
        decision_summary="test decision",
        iteration=1,
    )
    assert cp.id == "test-cp"
    assert len(cp.messages_snapshot) == 1


# ==================== Phase 3: 增强功能 ====================
print("\n⚡ Phase 3: 增强功能")


@test("MemoryStorage (SQLite 统一存储)")
def _():
    from openakita.memory.storage import MemoryStorage

    # 使用临时数据库（Windows 需要先关闭连接才能删除目录）
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test_memories.db")
        storage = MemoryStorage(db_path=db_path)

        # 保存记忆 (save_memory 接受 dict)
        mem_dict = {
            "id": "test-mem-001",
            "content": "Python 的 asyncio 库用于异步编程",
            "type": "FACT",
            "source": "test",
            "tags": ["python", "async"],
        }
        storage.save_memory(mem_dict)

        # 查询记忆
        mem = storage.get_memory("test-mem-001")
        assert mem is not None
        assert "asyncio" in mem["content"]

        # 批量保存
        mems = [
            {"id": f"test-batch-{i}", "content": f"测试记忆 {i}", "type": "FACT", "source": "test"}
            for i in range(5)
        ]
        storage.save_memories_batch(mems)

        # 计数
        count = storage.count()
        assert count >= 6, f"Expected at least 6, got {count}"

        # 导出
        export_path = os.path.join(tmpdir, "export.json")
        exported_count = storage.export_json(export_path)
        assert exported_count >= 6
        assert os.path.exists(export_path)

        # 删除
        deleted = storage.delete_memory("test-mem-001")
        assert deleted
        assert storage.get_memory("test-mem-001") is None

        # 显式关闭连接（Windows 必须）
        storage.close()
    finally:
        import shutil
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


@test("高频工具直接注入 (catalog)")
def _():
    from openakita.tools.catalog import HIGH_FREQ_TOOLS, ToolCatalog
    assert len(HIGH_FREQ_TOOLS) == 4
    assert "run_shell" in HIGH_FREQ_TOOLS
    assert "read_file" in HIGH_FREQ_TOOLS
    assert "write_file" in HIGH_FREQ_TOOLS
    assert "list_directory" in HIGH_FREQ_TOOLS


# ==================== Phase 4: 高级功能 ====================
print("\n🚀 Phase 4: 高级功能")


@test("Handoff 多 Agent 编排")
def _():
    from openakita.orchestration.handoff import (
        HandoffAgent, HandoffTarget, HandoffOrchestrator,
    )

    coder = HandoffAgent(
        name="coder",
        description="代码编写专家",
        system_prompt="你是一个代码编写专家",
        tools=["run_shell", "write_file"],
    )
    reviewer = HandoffAgent(
        name="reviewer",
        description="代码审查专家",
        system_prompt="你是一个代码审查专家",
        tools=["read_file"],
    )

    coder.add_handoff(reviewer, description="代码写完后需要审查")
    reviewer.add_handoff(coder, description="审查发现问题需要修改")

    assert len(coder.handoffs) == 1
    assert coder.handoffs[0].agent_name == "reviewer"
    assert coder.handoffs[0].tool_name == "transfer_to_reviewer"

    # 测试 handoff 工具生成
    tools = coder.get_handoff_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "transfer_to_reviewer"
    assert "input_schema" in tools[0]

    # 测试编排器
    orch = HandoffOrchestrator(agents=[coder, reviewer], entry_agent=coder)
    assert orch.current_agent.name == "coder"


@test("评估框架 - Metrics")
def _():
    from openakita.evaluation.metrics import EvalMetrics, EvalResult, TraceMetrics

    # 测试 TraceMetrics
    tm = TraceMetrics(
        trace_id="test-trace",
        total_iterations=5,
        total_tool_calls=10,
        total_input_tokens=5000,
        total_output_tokens=2000,
        total_duration_ms=30000,
        task_completed=True,
        tool_errors=1,
        tools_used=["run_shell", "read_file", "write_file"],
    )
    assert tm.unique_tools == 0  # 在 from_trace 时计算

    # 测试 EvalResult
    result = EvalResult(
        trace_id="test-trace",
        metrics=tm,
        judge_score=0.85,
        tags=["completed"],
    )
    assert result.is_good()

    # 测试 EvalMetrics.aggregate
    results = [
        EvalResult(
            trace_id=f"t{i}",
            metrics=TraceMetrics(
                trace_id=f"t{i}",
                total_iterations=i + 3,
                total_tool_calls=i * 2,
                total_input_tokens=1000 * (i + 1),
                total_output_tokens=500 * (i + 1),
                total_duration_ms=10000 * (i + 1),
                task_completed=i < 4,
                tool_errors=1 if i == 2 else 0,
            ),
            judge_score=0.8 if i < 4 else 0.3,
        )
        for i in range(5)
    ]
    metrics = EvalMetrics.aggregate(results)
    assert metrics.total_traces == 5
    assert metrics.task_completion_rate == 0.8
    assert metrics.avg_judge_score > 0

    # 测试格式化
    report_text = metrics.format_report()
    assert "任务完成率" in report_text
    assert "80.0%" in report_text


@test("评估框架 - Judge")
def _():
    from openakita.evaluation.judge import Judge, JudgeResult

    # 测试 JudgeResult 解析
    raw = '''```json
    {
        "scores": {"task_understanding": 0.9, "tool_usage": 0.8},
        "overall_score": 0.85,
        "reasoning": "表现不错",
        "suggestions": ["可以优化工具选择"],
        "failure_patterns": []
    }
    ```'''
    result = JudgeResult.from_llm_response("test", raw)
    assert result.overall_score == 0.85
    assert "表现不错" in result.reasoning
    assert len(result.suggestions) == 1


@test("评估框架 - Optimizer")
def _():
    from openakita.evaluation.optimizer import (
        FeedbackAnalyzer, FeedbackOptimizer, OptimizationAction,
    )
    from openakita.evaluation.metrics import EvalMetrics, EvalResult, TraceMetrics

    analyzer = FeedbackAnalyzer()

    # 创建低完成率场景
    results = [
        EvalResult(
            trace_id=f"t{i}",
            metrics=TraceMetrics(
                trace_id=f"t{i}",
                task_completed=i < 2,  # 只有 2/5 完成
                tool_errors=2 if i >= 2 else 0,
            ),
            judge_score=0.8 if i < 2 else 0.3,
            tags=["failed"] if i >= 2 else [],
        )
        for i in range(5)
    ]
    metrics = EvalMetrics.aggregate(results)
    actions = analyzer.analyze(metrics, results)

    # 低完成率应触发 memory 反馈
    memory_actions = [a for a in actions if a.action_type == "memory"]
    assert len(memory_actions) > 0, f"Expected memory action for low completion rate ({metrics.task_completion_rate})"


# ==================== 集成测试 ====================
print("\n🔗 集成测试")


@test("Config 新增配置项")
def _():
    from openakita.config import settings

    # 验证新增配置项存在
    assert hasattr(settings, "tracing_enabled")
    assert hasattr(settings, "tracing_export_dir")
    assert hasattr(settings, "tracing_console_export")
    assert hasattr(settings, "evaluation_enabled")
    assert hasattr(settings, "evaluation_output_dir")
    assert hasattr(settings, "orchestration_mode")

    # 验证默认值
    assert settings.orchestration_mode == "single"
    assert settings.tracing_enabled is False
    assert settings.evaluation_enabled is False


@test("main.py 追踪初始化")
def _():
    from openakita.tracing.tracer import get_tracer
    tracer = get_tracer()
    # main.py 的 _init_tracing 在 import 时已执行
    # tracing_enabled 默认 False，所以 tracer 应该是 disabled
    assert not tracer.enabled


@test("Agent 子模块初始化检查")
def _():
    """验证 Agent 类有初始化所有子模块的代码"""
    from openakita.core.agent import Agent

    # 通过检查 __init__ 源码来验证
    import inspect
    source = inspect.getsource(Agent.__init__)
    assert "AgentState" in source, "agent_state 未在 __init__ 中初始化"
    assert "ToolExecutor" in source, "tool_executor 未在 __init__ 中初始化"
    assert "ContextManager" in source, "context_manager 未在 __init__ 中初始化"
    assert "ResponseHandler" in source, "response_handler 未在 __init__ 中初始化"
    assert "SkillManager" in source, "skill_manager 未在 __init__ 中初始化"
    assert "PromptAssembler" in source, "prompt_assembler 未在 __init__ 中初始化"
    assert "ReasoningEngine" in source, "reasoning_engine 未在 __init__ 中初始化"


@test("Agent._chat_with_tools_and_context 委托给 ReasoningEngine")
def _():
    """验证核心方法已委托"""
    from openakita.core.agent import Agent
    import inspect
    source = inspect.getsource(Agent._chat_with_tools_and_context)
    assert "self.reasoning_engine.run" in source, \
        "_chat_with_tools_and_context 未委托给 reasoning_engine.run()"


@test("全模块导入链完整性")
def _():
    """验证所有新模块的完整导入链"""
    # Phase 1
    from openakita.core.agent_state import AgentState, TaskState, TaskStatus
    from openakita.tracing import AgentTracer, Span, SpanType, SpanStatus, Trace, get_tracer, set_tracer
    from openakita.tracing.exporter import FileExporter, ConsoleExporter
    from openakita.tools.errors import ToolError, ErrorType, classify_error

    # Phase 2
    from openakita.core.tool_executor import ToolExecutor
    from openakita.core.context_manager import ContextManager
    from openakita.core.response_handler import ResponseHandler
    from openakita.core.skill_manager import SkillManager
    from openakita.core.prompt_assembler import PromptAssembler
    from openakita.core.reasoning_engine import ReasoningEngine, Checkpoint, Decision

    # Phase 3
    from openakita.memory.storage import MemoryStorage

    # Phase 4
    from openakita.orchestration.handoff import HandoffAgent, HandoffTarget, HandoffOrchestrator
    from openakita.evaluation.metrics import EvalMetrics, EvalResult, TraceMetrics
    from openakita.evaluation.judge import Judge, JudgeResult
    from openakita.evaluation.runner import EvalRunner
    from openakita.evaluation.reporter import Reporter
    from openakita.evaluation.optimizer import FeedbackAnalyzer, FeedbackOptimizer, DailyEvaluator


# ==================== 汇总 ====================
print("\n" + "=" * 60)
print(f"📊 测试结果: {passed} 通过, {failed} 失败")
print("=" * 60)

if errors:
    print("\n❌ 失败详情:")
    for name, err in errors:
        print(f"  - {name}: {err}")

sys.exit(1 if failed > 0 else 0)
