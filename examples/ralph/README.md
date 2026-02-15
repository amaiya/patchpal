# Ralph Wiggum Technique for PatchPal

> "I'm learnding!" - Ralph Wiggum

The **Ralph Wiggum technique** is an iterative AI development methodology where an agent repeatedly works on a task until completion. Pioneered by [Geoffrey Huntley](https://ghuntley.com/ralph/), it's named after The Simpsons character and embodies the philosophy of persistent iteration despite setbacks.

---

## ⚠️ Critical Safety Warning

Ralph runs **fully autonomously** with permissions disabled. The agent can modify any file and run any shell command without prompts.

**Always use in isolated environments:**
- Docker/Podman containers (recommended)
- Dedicated VMs or test machines
- Throwaway projects with git history

**Never run on:**
- Production systems
- Your main development machine
- Repositories with uncommitted work
- Systems with valuable data

See [Safety Considerations](#safety-considerations) for detailed guidance.

---

## What is Ralph?

Ralph is fundamentally about **iteration over perfection**. Instead of building everything perfectly in one shot, you let the agent try, fail, learn, and try again - automatically.

### Key Principles

1. **Iteration > Perfection**: Let the loop refine the work
2. **Failures Are Data**: Deterministically bad means failures are predictable
3. **Operator Skill Matters**: Success depends on writing good prompts
4. **Persistence Wins**: Keep trying until success

### The Core Mechanism

```
1. Agent works on task
2. Agent tries to exit
3. Stop hook intercepts ← Key insight!
4. Same prompt fed back
5. Agent sees previous work in history
6. Agent adjusts approach
7. Repeat until completion promise found
```

The agent never actually "completes" until it outputs the completion promise. This forces it to review its own work, notice failures, and try different approaches.

## Quick Start

After `pip install patchpal`, autopilot is available immediately:

```bash
# Command-line usage
patchpal-autopilot \
  --prompt "Build a REST API with tests. When complete, output: <promise>COMPLETE</promise>" \
  --completion-promise "COMPLETE" \
  --max-iterations 30

# Using a prompt file
patchpal-autopilot \
  --prompt-file prompts/todo_api.md \
  --completion-promise "COMPLETE" \
  --max-iterations 50

# Python library
from patchpal.autopilot import autopilot_loop

autopilot_loop(
    prompt="Build a REST API with tests. Output: <promise>COMPLETE</promise>",
    completion_promise="COMPLETE",
    max_iterations=30
)
```

### The Stop Hook Implementation

```python
# The mechanism: Check for completion, or feed prompt back
for iteration in range(max_iterations):
    response = agent.run(prompt)  # Same prompt every time!

    if completion_promise in response:
        return response  # Done!

    # No completion - agent will see its previous work and try again
```

The agent's message history preserves all previous work, so each iteration builds on the last.

## Writing Effective Prompts

Good prompts are critical to Ralph's success.

### ✅ Good Prompt Structure

```markdown
# Task: [Clear, specific goal]

## Requirements
- Specific requirement 1
- Specific requirement 2
- Measurable success criteria

## Process
1. Write code
2. Run tests: run_shell("pytest -v")
3. If tests fail, debug and fix
4. Repeat until all tests pass

## Success Criteria
- All tests pass
- Coverage >80%
- No linter errors

## Escape Hatch
After 15 iterations if not complete:
- Document blocking issues in BLOCKED.md
- List attempted approaches

When complete, output: <promise>COMPLETE</promise>
```

### Key Elements

1. **Clear Completion Criteria**: What does "done" look like?
2. **Incremental Goals**: Break into phases
3. **Self-Correction Pattern**: Built-in feedback loop (write → test → fix → repeat)
4. **Escape Hatches**: Handle impossible tasks gracefully
5. **Explicit Completion Promise**: Use a unique string that won't appear accidentally

### Example: Good vs Bad

❌ **Bad (Too Vague)**
```markdown
Build a todo API and make it good.
```

✅ **Good (Clear & Specific)**
```markdown
Build a REST API for todos.

Requirements:
- Flask app with CRUD endpoints (GET, POST, PUT, DELETE)
- Input validation (title required, max 200 chars)
- Unit tests with pytest (>80% coverage)
- README with API documentation

Process:
1. Create app.py with routes
2. Write tests in test_app.py
3. Run: run_shell("pytest test_app.py -v")
4. If any fail, debug and fix
5. Repeat until all green

Output: <promise>COMPLETE</promise> when done.
```

## Safety Considerations

### Why Ralph Is Dangerous

Ralph disables PatchPal's permission system (`PATCHPAL_REQUIRE_PERMISSION=false`), which means:

- ✅ Full autonomy - no permission prompts
- ❌ No sandboxing - full user account access
- ❌ No command filtering - can run any shell command
- ❌ No file restrictions - can modify anything
- ❌ Multiple iterations without oversight

### Recommended: Run in Isolated Environments

**Option 1: Docker Container (Recommended)**

```bash
# Create Dockerfile
cat > Dockerfile.autopilot <<EOF
FROM python:3.11-slim
RUN pip install patchpal
WORKDIR /workspace
EOF

# Build and run
docker build -f Dockerfile.autopilot -t autopilot-env .

docker run -it --rm \
  -v $(pwd):/workspace \
  --memory="2g" \
  --cpus="2" \
  autopilot-env \
  patchpal-autopilot --prompt-file task.md --completion-promise "DONE"
```

**Option 2: Dedicated Sandbox Machine**

```bash
# Use a separate VM or EC2 instance
ssh ralph-sandbox
cd /workspace/throwaway-project
patchpal-autopilot --prompt-file task.md --completion-promise "DONE"
```

**Option 3: Git Worktree (Minimal Protection)**

```bash
# Create isolated branch
git worktree add ../autopilot-sandbox -b autopilot-experiment
cd ../autopilot-sandbox

# Run autopilot
patchpal-autopilot --prompt-file task.md --completion-promise "DONE"

# Review and merge or discard
git diff main
```

### Safety Best Practices

**1. Always Use Version Control**
```bash
git add -A && git commit -m "Before autopilot"
patchpal-autopilot --prompt-file task.md --completion-promise "DONE"
git diff HEAD  # Review changes
git reset --hard HEAD  # Rollback if needed
```

**2. Test with Low Iterations First**
```bash
# Validate prompt with limited iterations
patchpal-autopilot --prompt "..." --completion-promise "DONE" --max-iterations 5

# Increase gradually: 10, 20, 50
```

**3. Add Safety Constraints in Prompt**
```markdown
## Safety Constraints
- ONLY modify files in src/ and tests/ directories
- DO NOT modify: package.json, .env, config files
- DO NOT run: sudo, rm -rf, git push
- If blocked, document in BLOCKED.md and stop
```

**4. Use Read-Only Mode for Testing**
```bash
export PATCHPAL_READ_ONLY=true
patchpal-autopilot --prompt-file test.md --completion-promise "DONE" --max-iterations 5
```

### When to Use Ralph

| ✅ Safe Use Cases | ❌ Unsafe Without Sandboxing |
|------------------|------------------------------|
| Sandboxed/isolated environments | Production codebases on main machine |
| Throwaway projects | Repositories with uncommitted work |
| Git repos with committed baseline | Systems with valuable data |
| Well-defined tasks | Critical infrastructure files |
| Iterative refinement | Your daily-use laptop |

## Advanced Patterns

### Multi-Phase Projects

For complex projects, break them into sequential phases:

```bash
# Example: multi_phase_todo_api_example.py
python multi_phase_todo_api_example.py
```

### Parallel Ralph Loops

Run multiple autopilot loops simultaneously:

```bash
git worktree add ../project-auth -b feature/auth
git worktree add ../project-api -b feature/api

# Terminal 1
cd ../project-auth && patchpal-autopilot --prompt-file auth.md --completion-promise "DONE"

# Terminal 2
cd ../project-api && patchpal-autopilot --prompt-file api.md --completion-promise "DONE"
```

### Overnight Processing (Sandboxed Only)

```bash
# ✅ SAFE: Dedicated sandbox machine
ssh autopilot-sandbox
nohup patchpal-autopilot --prompt-file task.md --completion-promise "DONE" \
  --max-iterations 100 > autopilot.log 2>&1 &

# ❌ UNSAFE: Your daily laptop (DO NOT DO THIS)
```

### Prompt Tuning

Iteratively improve prompts based on failures:

```markdown
# Version 1 → Fails after 10 iterations
Build a REST API.

# Version 2 → Add explicit validation
Build a REST API.
- Write tests in test_app.py
- Run: run_shell("pytest -v")
- Fix failures until all pass
- Output: COMPLETE when pytest succeeds

# Version 3 → Add escape hatch
Build a REST API.
- Write tests, run pytest
- Fix failures until all pass
- If stuck after 10 iterations, document in BLOCKED.md
- Output: COMPLETE when done
```

## Cost Optimization

### Use Local Models (Zero Cost)

```bash
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal-autopilot --model hosted_vllm/openai/gpt-oss-20b \
  --prompt-file task.md --completion-promise "COMPLETE"
```

### Cost Control Tips

1. Test with `--max-iterations 5` first to validate prompts
2. Use cheaper models for simple tasks
3. Break large tasks into phases
4. Monitor token usage in output

## Troubleshooting

**Never Completes**
- Make completion promise more specific
- Add intermediate checkpoints
- Increase max iterations
- Review if task is achievable

**Repeats Same Mistake**
- Add explicit instructions about the failure
- Include self-correction: "If X fails, try Y"
- Add escape hatch after N failures

**High API Costs**
- Use local models (vLLM/Ollama)
- Test with low iterations first
- Break into smaller phases

## Real-World Results

- **6 repos at Y Combinator hackathon** - Generated overnight
- **$50k contract for $297 in API costs** - Complete, tested, reviewed
- **CURSED programming language** - Built over 3 months
- **Test-driven development** - Excellent for TDD workflows

## Files in This Example

```
examples/ralph/
├── README.md                           # This guide
├── simple_autopilot_example.py         # Basic Python library usage
├── multi_phase_todo_api_example.py     # Multi-phase sequential example
└── prompts/                            # Example prompt templates
    ├── todo_api.md
    ├── fix_tests.md
    └── refactor.md
```

**Custom Tools**: Autopilot automatically loads custom tools from `~/.patchpal/tools/` (same as interactive CLI).

## Related Resources

- **[Ralph Technique Explained](https://ghuntley.com/ralph/)** - Geoffrey Huntley's comprehensive guide
- **[A Brief History of Ralph](https://www.humanlayer.dev/blog/brief-history-of-ralph)** - Philosophy and history
- **[Ralph Wiggum - Awesome Claude](https://awesomeclaude.ai/ralph-wiggum)** - Prompt templates and patterns
- **[Matt Pocock's Tutorial](https://www.youtube.com/watch?v=_IK18goX4X8)** - "Ship working code while you sleep"
- **[AI That Works Podcast](https://www.youtube.com/watch?v=fOPvAPdqgPo)** - 75-min deep dive with Geoff Huntley
- **[CURSED Language](https://cursed-lang.org)** - Programming language built with Ralph
- **[Awesome Ralph](https://github.com/snwfdhmp/awesome-ralph)** - Curated resources

## License

Part of PatchPal, follows the same license.
