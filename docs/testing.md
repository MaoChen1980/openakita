# Testing Guide

OpenAkita includes a comprehensive testing framework with 300+ test cases.

## Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| QA/Basic | 30 | Math, programming knowledge |
| QA/Reasoning | 35 | Logic, code comprehension |
| QA/Multi-turn | 35 | Context memory, instruction following |
| Tools/Shell | 40 | Command execution |
| Tools/File | 30 | File operations |
| Tools/API | 30 | HTTP requests |
| Search/Web | 40 | Web search |
| Search/Code | 30 | Code search |
| Search/Docs | 30 | Documentation search |
| **Total** | **300** | |

## Running Tests

### All Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=src/openakita --cov-report=html
```

### Specific Categories

```bash
# Only QA tests
pytest tests/test_qa.py -v

# Only tool tests
pytest tests/test_tools.py -v

# Only search tests
pytest tests/test_search.py -v
```

### Self-Check Mode

```bash
# Quick check (core functionality)
openakita selfcheck --quick

# Full check (all 300 tests)
openakita selfcheck --full

# With auto-fix on failure
openakita selfcheck --fix
```

## Test Structure

### Test File Organization

```
tests/
├── test_qa.py            # Q&A tests
├── test_tools.py         # Tool tests
├── test_search.py        # Search tests
├── test_integration.py   # Integration tests
└── fixtures/
    ├── sample_files/     # Test files
    └── mock_responses/   # Mock API responses
```

### Test Case Format

```python
# tests/test_qa.py
import pytest
from openakita.testing.runner import TestRunner

class TestBasicQA:
    """Basic question-answering tests."""
    
    @pytest.mark.asyncio
    async def test_math_addition(self, agent):
        """Agent can perform basic math."""
        response = await agent.process("What is 2 + 2?")
        assert "4" in response
    
    @pytest.mark.asyncio
    async def test_programming_knowledge(self, agent):
        """Agent knows programming concepts."""
        response = await agent.process("What is a Python decorator?")
        assert "function" in response.lower()
```

## Built-in Test Runner

### TestRunner Class

```python
from openakita.testing.runner import TestRunner, TestCase

runner = TestRunner()

# Add test cases
runner.add_case(TestCase(
    id="qa_math_001",
    category="qa/basic",
    input="What is 15 * 7?",
    expected_contains=["105"],
    timeout=30
))

# Run tests
results = await runner.run_all()
print(f"Passed: {results.passed}/{results.total}")
```

### Test Case Definition

```python
@dataclass
class TestCase:
    id: str                    # Unique identifier
    category: str              # Test category
    input: str                 # User input
    expected_contains: list    # Expected substrings in output
    expected_not_contains: list = None  # Should not appear
    timeout: int = 60          # Timeout in seconds
    requires_tools: list = None  # Required tools
    setup: Callable = None     # Setup function
    teardown: Callable = None  # Teardown function
```

## Judge System

The judge evaluates test results:

```python
from openakita.testing.judge import Judge

judge = Judge()

verdict = judge.evaluate(
    expected="The answer is 42",
    actual="Based on my calculation, the answer is 42.",
    criteria=["exact_match", "contains", "semantic"]
)

print(verdict.passed)  # True
print(verdict.score)   # 0.95
print(verdict.reason)  # "Contains expected value"
```

### Evaluation Criteria

| Criteria | Description |
|----------|-------------|
| `exact_match` | Output exactly matches expected |
| `contains` | Output contains expected substring |
| `not_contains` | Output does not contain string |
| `semantic` | Semantically similar (uses LLM) |
| `regex` | Matches regular expression |
| `json_valid` | Output is valid JSON |
| `code_runs` | Code in output executes successfully |

## Auto-Fix System

When tests fail, OpenAkita can attempt automatic fixes:

```python
from openakita.testing.fixer import Fixer

fixer = Fixer()

# Analyze failure
analysis = await fixer.analyze(
    test_case=failed_test,
    actual_output=output,
    error_message=error
)

# Attempt fix
if analysis.fixable:
    fix = await fixer.generate_fix(analysis)
    await fixer.apply_fix(fix)
    
    # Re-run test
    result = await runner.run_case(failed_test)
```

### Fix Categories

| Category | Auto-Fix Support |
|----------|------------------|
| Missing import | ✅ Yes |
| Syntax error | ✅ Yes |
| Type mismatch | ✅ Yes |
| Logic error | ⚠️ Sometimes |
| Design flaw | ❌ No |

## Writing Tests

### Best Practices

1. **One assertion per test** when possible
2. **Use descriptive names** that explain what's tested
3. **Include edge cases** (empty input, large data, etc.)
4. **Mock external services** to ensure reproducibility
5. **Set appropriate timeouts** for async operations

### Example: Tool Test

```python
@pytest.mark.asyncio
async def test_file_write_read(self, agent, tmp_path):
    """Agent can write and read files."""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"
    
    # Write file
    response = await agent.process(
        f"Write '{content}' to {test_file}"
    )
    assert test_file.exists()
    
    # Read file
    response = await agent.process(
        f"Read the contents of {test_file}"
    )
    assert content in response
```

### Example: Multi-turn Test

```python
@pytest.mark.asyncio
async def test_context_memory(self, agent):
    """Agent remembers context across turns."""
    # First turn
    await agent.process("My name is Alice")
    
    # Second turn - should remember
    response = await agent.process("What is my name?")
    assert "Alice" in response
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Run tests
        run: pytest tests/ -v --cov=src/openakita
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Tests

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG pytest tests/test_qa.py -v -s
```

### Run Single Test

```bash
pytest tests/test_qa.py::TestBasicQA::test_math_addition -v
```

### Interactive Debugging

```python
@pytest.mark.asyncio
async def test_with_debug(self, agent):
    import pdb; pdb.set_trace()
    response = await agent.process("Test input")
```

## Performance Testing

```python
import time

@pytest.mark.asyncio
async def test_response_time(self, agent):
    """Response should be under 5 seconds."""
    start = time.time()
    await agent.process("Simple question")
    elapsed = time.time() - start
    assert elapsed < 5.0
```

## Test Data

### Sample Files

Test files are in `tests/fixtures/sample_files/`:

```
sample_files/
├── text/
│   ├── simple.txt
│   └── unicode.txt
├── code/
│   ├── python_sample.py
│   └── javascript_sample.js
└── data/
    ├── sample.json
    └── sample.csv
```

### Mock Responses

Mock API responses in `tests/fixtures/mock_responses/`:

```python
# Loaded automatically in tests
MOCK_CLAUDE_RESPONSE = {
    "content": [{"type": "text", "text": "Mock response"}],
    "stop_reason": "end_turn"
}
```
