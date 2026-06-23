
# Autopilot Mode

**Autopilot mode** enables autonomous iterative development where the agent repeatedly works on a task until completion. Based on the ["Ralph Wiggum technique"](https://ghuntley.com/ralph/) pioneered by Geoffrey Huntley, it embodies persistent iteration over perfection.

⚠️ **CRITICAL SAFETY WARNING**: Autopilot disables PatchPal's permission system. **ONLY use in isolated environments** (Docker containers, VMs, throwaway projects). See [examples/ralph/](https://github.com/amaiya/patchpal/tree/main/examples/ralph) for comprehensive safety guidelines.

### Quick Start

```bash
# After pip install patchpal, autopilot is available immediately

# RECOMMENDED: Use patchpal-sandbox for safe isolation
patchpal-sandbox --env-file .env -- autopilot \
  --prompt-file task.md \
  --max-iterations 50

# Option 1: Direct command (⚠️ use only in safe/isolated environments)
patchpal-autopilot \
  --prompt-file task.md \
  --max-iterations 50

# Option 2: Use as a Python library
python -c "
from patchpal.cli.autopilot import autopilot_loop
autopilot_loop(
    prompt='Build a calculator with tests',
    completion_promise='COMPLETE',
    max_iterations=20
)
"
```

**Note**: The completion promise defaults to "COMPLETE" and is automatically appended to your prompts. You can customize it with `--completion-promise "DONE"` if needed. No need to include "Output: <promise>COMPLETE</promise>" in your task description.

**Custom Tools**: Autopilot automatically loads custom tools from both `~/.patchpal/tools/` (global) and `.patchpal/tools/` (repository-specific), same as the interactive CLI. See [Custom Tools](../features/custom-tools.md) for details.

### How It Works

The key insight: The agent sees its previous work in conversation history and can adjust its approach, notice failures, and try different solutions automatically.

```
1. Agent works on task
2. Agent tries to exit
3. Stop hook intercepts ← Key mechanism!
4. Same prompt fed back
5. Agent sees previous work in history
6. Agent adjusts approach
7. Repeat until completion promise found
```

The agent never actually "completes" until it outputs the completion promise string.

### Key Principles

- **Iteration > Perfection**: Let the loop refine the work, don't aim for perfect first try
- **Failures Are Data**: Deterministically bad means failures are predictable and informative
- **Operator Skill Matters**: Success depends on writing good prompts, not just having a good model
- **Persistence Wins**: Keep trying until success—the loop handles retry logic automatically

### Writing Effective Prompts

Good autopilot prompts have:

**1. Clear Completion Criteria**
```markdown
# Success Criteria
- All tests pass (pytest -v shows green)
- Coverage >80%
- No linter errors
- README with API documentation
```

Note: You don't need to include the completion promise in your prompt - it's automatically added.

**2. Self-Correction Pattern**
```markdown
# Process
1. Write code in app.py
2. Write tests in test_app.py
3. Run tests: run_shell("pytest test_app.py -v")
4. If any fail, debug and fix
5. Repeat until all pass
```

**3. Incremental Goals**
```markdown
# Requirements
Phase 1: Core CRUD operations
Phase 2: Input validation
Phase 3: Error handling
Phase 4: Tests (>80% coverage)
```

**4. Escape Hatch**
```markdown
# If Stuck
After 10 iterations without progress:
- Document blocking issues in BLOCKED.md
- List attempted approaches
- Suggest alternatives
```

### Real-World Examples

See [examples/ralph/](https://github.com/amaiya/patchpal/tree/main/examples/ralph) for complete examples:
- **simple_autopilot_example.py**: Basic calculator task
- **multi_phase_todo_api_example.py**: Multi-phase API build (3 sequential phases)
- **prompts/**: Example prompt templates for different task types

### Using as a Python Library

```python
from patchpal.cli.autopilot import autopilot_loop

result = autopilot_loop(
    prompt="""
Build a REST API for todos.

Requirements:
- Flask app with CRUD endpoints
- Input validation (title required, max 200 chars)
- Unit tests with pytest (>80% coverage)
- All tests passing

Process:
1. Create app.py with routes
2. Write tests in test_app.py
3. Run: run_shell("pytest test_app.py -v")
4. Fix failures and retry
    """,
    completion_promise="COMPLETE",
    max_iterations=30,
    model="anthropic/claude-sonnet-4-5"  # optional
)

if result:
    print("✅ Task completed successfully!")
else:
    print("⚠️ Did not complete within max iterations")
```

### Safety: Sandboxed Environments Only

**Why Isolation Is Critical:**

Autopilot mode automatically disables PatchPal's permission system (`PATCHPAL_REQUIRE_PERMISSION=false`):
- No permission prompts for file modifications
- No permission prompts for shell commands
- Multiple iterations without human oversight
- Potential for catastrophic mistakes

**Note:** When using `patchpal-sandbox` in **interactive mode** (without the `autopilot` subcommand), permissions remain **ENABLED** by default. Permissions are only automatically disabled when you explicitly use the `autopilot` subcommand or `patchpal-autopilot` command.

**Recommended Isolation:**

**Option 1: Use patchpal-sandbox (Easiest - Recommended)**

PatchPal includes `patchpal-sandbox`, a built-in command that automatically runs PatchPal in an isolated Docker/Podman container:

```bash
# Interactive mode (permissions enabled)
patchpal-sandbox --env-file .env -- --model anthropic/claude-sonnet-4-5

# Autopilot mode (permissions disabled automatically)
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file task.md

# With local Ollama model (requires --host-network)
patchpal-sandbox --host-network -- autopilot \
  --model ollama_chat/gpt-oss:120b \
  --prompt "Build a calculator with tests"
```

**Features:**
- ✅ Pre-built image with patchpal installed (fast startup - no pip install delay)
- ✅ Auto-detects Docker/Podman (prefers Podman for rootless)
- ✅ Auto-sets `OLLAMA_CONTEXT_LENGTH` for Ollama models (8192 for agents, 32768 for reasoning models)
- ✅ Loads API keys from `.env` file
- ✅ Mounts current directory as `/workspace`
- ✅ Auto-mounts `~/.patchpal` for custom tools and config
- ✅ Custom tools work automatically (from `~/.patchpal/tools/` and `<repo>/.patchpal/tools/`)
- ✅ Auto-mounts SSL certificates for corporate networks
- ✅ Clean environment on each run (`--rm` flag)

**Performance:**
- First run: Downloads pre-built image (~150MB, one-time)
- Subsequent runs: Start instantly (no pip install needed)
- For latest PyPI version: Use `--image python:3.11-slim` (10-30s slower startup)

See `patchpal-sandbox --help` for all options and examples.

**Option 2: Docker/Podman Command** (More Control)

Using the pre-built patchpal-sandbox image (recommended - fast startup):
```bash
# Using pre-built image (no pip install needed)
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --memory="2g" --cpus="2" \
  ghcr.io/amaiya/patchpal-sandbox:latest \
  bash -c "patchpal-autopilot --prompt-file task.md"
```

Using standard Python image (installs latest patchpal from PyPI):
```bash
# Using python:3.11-slim (slower - requires pip install)
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --memory="2g" --cpus="2" \
  python:3.11-slim bash

# Inside container
pip install patchpal
patchpal-autopilot --prompt-file task.md
```

**Option 3: Dedicated VM/Server** (Best for Production Automation)
```bash
# Use a separate machine/VM with no access to production
ssh autopilot-sandbox
cd /workspace/throwaway-project
patchpal-autopilot --prompt-file task.md
```

### Best Practices

**Always:**
- ✅ Use version control (commit before running)
- ✅ Run in isolated environments
- ✅ Start with low max-iterations (5-10) to validate prompts
- ✅ Monitor with `git status` or `watch -n 2 'git status --short'`
- ✅ Review all changes before committing

**Never:**
- ❌ Run on codebases in production
- ❌ Run on your main development machine without container
- ❌ Leave running unattended on important systems

### Real-World Results

The Ralph Wiggum technique has been successfully used for:
- **6 repos at Y Combinator hackathon** - Generated overnight
- **$50k contract for $297 in API costs** - Complete tested project
- **CURSED programming language** - Built over 3 months
- **Test-driven development** - Excellent for TDD workflows

See [examples/ralph/](https://github.com/amaiya/patchpal/blob/main/examples/ralph/) for comprehensive documentation, safety guidelines, and more examples.

### Learn More

- **Comprehensive Guide**: [examples/ralph/](https://github.com/amaiya/patchpal/tree/main/examples/ralph) - Safety, prompts, patterns, troubleshooting
- **Ralph Wiggum Technique Origins**:
  - https://www.humanlayer.dev/blog/brief-history-of-ralph
  - https://awesomeclaude.ai/ralph-wiggum
  - https://github.com/ghuntley/ralph
