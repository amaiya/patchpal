# Subtask Mode - Context Isolation for Local Models

Subtask mode runs tasks with **isolated context**, creating a fresh agent instance that only sees the task prompt, not your entire conversation history.

## Why This Helps Local Models

Local models often struggle with large context windows. Subtask mode addresses this by:

1. **Fresh Context**: Subtask starts with ~5K tokens (system prompt + task) instead of inheriting your 50K+ token conversation
2. **Focused Attention**: Agent isn't distracted by unrelated conversation history
3. **Result-Only Injection**: Parent only sees the final result, not all the exploratory tool calls
4. **Iterative Execution**: Can retry the task multiple times within the isolated context

## When to Use Subtask Mode

- **Complex sub-problems** that require multiple tool calls and iteration
- **Iterative tasks**: "Write tests, run them, fix failures, repeat until passing"
- **Large conversations**: When your main context is >50K tokens
- **Local models**: With limited context windows (e.g., 32K tokens)
- **Research tasks**: Gather info from many files without polluting main context

## Interactive Usage

```bash
patchpal> /subtask Create User model with SQLAlchemy, write tests, ensure all pass

Max iterations? [10]: 5
Completion signal? [<SUBTASK_DONE>]:

────────────────────────────────────────────────────────────────────────────────
🔹 Subtask Mode: Running with isolated context
   Parent context: 87,234 tokens | Subtask context: 4,891 tokens
────────────────────────────────────────────────────────────────────────────────

🔄 Subtask iteration 1/5
[Agent works in fresh context...]

✓ Subtask completed in 2 iteration(s)

────────────────────────────────────────────────────────────────────────────────
🔹 Subtask Complete: Result injected back to parent
   Parent: 87,234 → 88,156 tokens | Subtask used: 12,345 tokens
   Subtask LLM calls: 8 | Tokens: 23,456
   Subtask cost: $0.0234
────────────────────────────────────────────────────────────────────────────────

[Subtask Result]

Created User model with tests. All tests passing...
```

## Python API Usage

```python
from patchpal.agent import create_agent

agent = create_agent()

# Main conversation builds up context
agent.run("Show me the project structure")
agent.run("Explain the authentication flow")
# ... context is now at 80K tokens

# Delegate complex task to subtask with fresh context
result = agent.run_subtask(
    task_prompt="""
    Create a User model with SQLAlchemy:
    - Fields: id, username, email, password_hash, created_at
    - Add proper indexes
    - Write tests in test_models.py
    - Run tests with pytest
    - Fix any failures
    - Output <SUBTASK_DONE> when all tests pass
    """,
    max_iterations=10,
    completion_signal="<SUBTASK_DONE>"
)

# Continue main conversation - only has the result, not all the work
agent.run("Great! Now create the login endpoint")
```

## How It Works

1. **Create Fresh Agent**: `create_agent()` with same config but empty history
2. **Run Task**: Subtask agent iterates until completion signal found
3. **Aggregate Costs**: Token/cost usage rolled up to parent
4. **Inject Result**: Only final response added to parent's context

## Comparison to OpenCode Subagents

| Feature | OpenCode Subagents | PatchPal Subtask Mode |
|---------|-------------------|----------------------|
| **Context Isolation** | ✅ Separate sessions | ✅ Fresh agent instance |
| **Complexity** | High (~2000 lines) | Low (~150 lines) |
| **Parallel Execution** | ✅ Multiple subagents | ❌ Sequential only |
| **Tool Permissions** | ✅ Per-agent configs | ✅ Inherited from parent |
| **Result Injection** | ✅ Via tool response | ✅ As assistant message |
| **Local Model Benefit** | ✅ Small context | ✅ Small context |

## Tips

1. **Be Specific**: Include clear completion criteria in your task prompt
2. **Set Realistic Iterations**: Complex tasks may need 10-15 iterations
3. **Use Completion Signals**: Make them unique to avoid false positives
4. **Monitor Costs**: Check `/status` to see subtask token usage

## Example: Multi-Phase Build

```python
# Phase 1: Data models (fresh context)
agent.run_subtask("Create SQLAlchemy models with tests. Output <MODELS_DONE> when passing")

# Phase 2: API endpoints (another fresh context)
agent.run_subtask("Create Flask API endpoints with tests. Output <API_DONE> when passing")

# Phase 3: Authentication (another fresh context)
agent.run_subtask("Add JWT authentication with tests. Output <AUTH_DONE> when passing")

# Main conversation stays clean - only has 3 results, not 100+ tool calls
```

## Troubleshooting

**Subtask doesn't complete**:
- Increase `max_iterations`
- Make completion criteria clearer
- Check if task is too complex (break into smaller subtasks)

**Parent context still growing**:
- Subtask results can be large - they're full responses
- Consider extracting just the key info: "Summarize that subtask result in 2 sentences"

**Costs higher than expected**:
- Subtask creates a new agent instance (pays context setup cost)
- Use `/status` to see subtask vs parent token usage
- Consider using subtasks only for truly complex sub-problems
