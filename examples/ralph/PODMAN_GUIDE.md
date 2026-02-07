# Running Ralph Safely with Podman

This guide provides step-by-step instructions for running Ralph in an isolated Podman container for maximum safety.

## Why Use Podman?

Ralph disables PatchPal's permission system (`PATCHPAL_REQUIRE_PERMISSION=false`) for autonomous operation, which means:

- ❌ No permission prompts for file modifications or shell commands
- ❌ No sandboxing - full user account access
- ❌ Potential for accidental damage

**Solution**: Run Ralph in an isolated Podman container with:
- ✅ Resource limits (CPU, memory)
- ✅ Network isolation (optional)
- ✅ Volume mounting (changes only affect mounted directory)
- ✅ Easy cleanup (container is ephemeral)

## Prerequisites

- Podman installed (`podman --version`)
- PatchPal examples cloned (or at least `ralph.py`)
- API key for Anthropic or OpenAI (get from their consoles)

## Quick Start (TL;DR)

```bash
# 1. Create sandbox
mkdir ~/ralph-sandbox && cd ~/ralph-sandbox
git init && touch .gitkeep && git add . && git commit -m "Initial"

# 2. Copy Ralph script
cp /path/to/patchpal/examples/ralph/ralph.py .

# 3. Create Dockerfile
cat > Dockerfile.ralph <<'EOF'
FROM python:3.11-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir patchpal
WORKDIR /workspace
CMD ["/bin/bash"]
EOF

# 4. Build image
podman build -f Dockerfile.ralph -t ralph-env .

# For WSL users, use this instead:
# podman build --cgroup-manager=cgroupfs -f Dockerfile.ralph -t ralph-env .

# 5. Set up API key
cat > .env.ralph <<'EOF'
ANTHROPIC_API_KEY=your-api-key-here
PATCHPAL_MODEL=anthropic/claude-sonnet-4-5
PATCHPAL_REQUIRE_PERMISSION=false
EOF

# 6. Copy example prompts
cp /path/to/patchpal/examples/ralph/prompts/calculator.md .

# OR create a simple test prompt inline
cat > prompt_simple.md <<'EOF'
# Task: Create Hello World

Create hello.py with a hello() function that returns "Hello, World!".
Create test_hello.py with pytest tests.
Run tests: run_shell("pytest test_hello.py -v")
Fix failures until tests pass.

When done, output: <promise>COMPLETE</promise>
EOF

# 7. Run Ralph!
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  --memory="2g" --cpus="2" \
  ralph-env \
  python ralph.py --prompt-file prompt_simple.md \
    --completion-promise "COMPLETE" --max-iterations 10

# Or use the calculator example
# python ralph.py --prompt-file calculator.md --completion-promise "COMPLETE" --max-iterations 10
```

## Detailed Step-by-Step Guide

### Step 1: Create an Isolated Workspace

Create a dedicated directory for Ralph experiments:

```bash
# Create sandbox directory
mkdir -p ~/ralph-sandbox
cd ~/ralph-sandbox

# Initialize git for easy rollback
git init
git config user.name "Ralph Test"
git config user.email "ralph@test.local"

# Create initial commit
touch .gitkeep
git add .gitkeep
git commit -m "Initial commit - Ralph sandbox"
```

**Why git?** You can easily review changes with `git diff` and rollback with `git reset --hard HEAD` if Ralph makes mistakes.

### Step 2: Copy Ralph Script

Get the Ralph script from the PatchPal repository:

```bash
# If you have PatchPal cloned locally
cp /path/to/patchpal/examples/ralph/ralph.py .

# Verify it's there
ls -lh ralph.py
```

### Step 3: Create Dockerfile

Create a Dockerfile for the Ralph environment:

```bash
cat > Dockerfile.ralph <<'EOF'
FROM python:3.11-slim

# Install system dependencies (git needed for operations)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PatchPal
RUN pip install --no-cache-dir patchpal

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
EOF
```

**What this does:**
- Uses official Python 3.11 slim image (minimal size)
- Installs git (required for some operations)
- Installs PatchPal from PyPI
- Sets `/workspace` as working directory

### Step 4: Build the Podman Image

Build the container image:

```bash
# Build the image (Linux/macOS)
podman build -f Dockerfile.ralph -t ralph-env .

# For WSL (Windows Subsystem for Linux), add cgroup-manager flag
podman build --cgroup-manager=cgroupfs -f Dockerfile.ralph -t ralph-env .

# Verify it built successfully
podman images | grep ralph-env
```

**WSL Note:** On Windows Subsystem for Linux, you need `--cgroup-manager=cgroupfs` because systemd user sessions aren't available. This prevents the warning about cgroupv2 manager.

This creates a reusable image named `ralph-env`. You only need to build once.

### Step 5: Configure API Credentials

Create an environment file with your API credentials:

```bash
cat > .env.ralph <<'EOF'
# Anthropic API key (get from https://console.anthropic.com/)
ANTHROPIC_API_KEY=your-api-key-here

# Or use OpenAI instead
# OPENAI_API_KEY=your-openai-key-here
# PATCHPAL_MODEL=openai/gpt-4o

# PatchPal configuration
PATCHPAL_MODEL=anthropic/claude-sonnet-4-5
PATCHPAL_REQUIRE_PERMISSION=false
EOF
```

**⚠️ IMPORTANT:** Replace `your-api-key-here` with your actual API key!

**Security note:** `.env.ralph` contains sensitive credentials. Add it to `.gitignore`:

```bash
echo ".env.ralph" >> .gitignore
git add .gitignore
git commit -m "Ignore API credentials"
```

### Step 6: Create a Test Prompt

Start with a simple prompt to verify everything works. You can either copy one of the example prompts or create your own:

**Option A: Use an example prompt (recommended)**

```bash
# Copy the calculator example from PatchPal repo
cp /path/to/patchpal/examples/ralph/prompts/calculator.md .

# Verify it's there
cat calculator.md
```

**Option B: Create a minimal test prompt**

```bash
cat > prompt_simple.md <<'EOF'
# Task: Create Hello World

Create hello.py with a hello() function that returns "Hello, World!".
Create test_hello.py with pytest tests.
Run tests: run_shell("pytest test_hello.py -v")
Fix failures until tests pass.

When done, output: <promise>COMPLETE</promise>
EOF
```

**Option C: Create the calculator example inline**

```bash
cat > calculator.md <<'EOF'
# Task: Create a Simple Calculator

Build a Python calculator module with tests.

## Requirements
- Create calculator.py with functions: add, subtract, multiply, divide
- Handle division by zero (raise ValueError)
- Create test_calculator.py with pytest tests
- All tests must pass

## Process
1. Create calculator.py with four functions
2. Create test_calculator.py with tests for each function
3. Run tests: run_shell("pytest test_calculator.py -v")
4. Fix any failures
5. Repeat until all tests pass

## Success Criteria
- All 4 functions work correctly
- Division by zero raises ValueError with message
- All pytest tests pass
- No errors or warnings

When complete, output: <promise>COMPLETE</promise>
EOF
```

### Step 7: Run Ralph in Podman

Now run Ralph in the isolated container:

```bash
# Using the calculator example (recommended for first test)
podman run -it --rm \
  --name ralph-test \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  --memory="2g" \
  --cpus="2" \
  ralph-env \
  python ralph.py --prompt-file calculator.md \
    --completion-promise "COMPLETE" --max-iterations 10

# Or use the minimal hello world example
# podman run -it --rm \
#   -v $(pwd):/workspace:Z \
#   --env-file .env.ralph \
#   --memory="2g" --cpus="2" \
#   ralph-env \
#   python ralph.py --prompt-file prompt_simple.md \
#     --completion-promise "COMPLETE" --max-iterations 10
```

**Flags explained:**
- `-it` - Interactive terminal
- `--rm` - Remove container after exit (ephemeral)
- `--name ralph-test` - Name the container
- `-v $(pwd):/workspace:Z` - Mount current directory (`:Z` for SELinux)
- `--env-file .env.ralph` - Load environment variables
- `--memory="2g"` - Limit to 2GB RAM
- `--cpus="2"` - Limit to 2 CPU cores
- `ralph-env` - Use the image we built
- `python ralph.py ...` - Run Ralph with options

### Step 8: Monitor Ralph's Progress

While Ralph runs, open another terminal to monitor:

```bash
# Watch file changes
watch -n 2 'cd ~/ralph-sandbox && ls -lah'

# Watch git status
watch -n 2 'cd ~/ralph-sandbox && git status --short'

# Monitor resources (optional)
podman stats ralph-test
```

### Step 9: Review Ralph's Work

After Ralph completes (or you stop it with Ctrl-C):

```bash
# See what Ralph created
ls -lah

# Review all changes
git status
git diff

# Check if tests pass
pytest -v

# If you like the results, commit them
git add -A
git commit -m "Ralph generated calculator"

# If you don't like the results, rollback everything
git reset --hard HEAD
git clean -fd
```

### Step 10: Try Real Examples

Once comfortable with the basic example, try the provided prompts:

```bash
# Copy example prompts
cp /path/to/patchpal/examples/ralph/prompts/*.md .

# Run the Todo API example (more complex)
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  --memory="4g" \
  --cpus="4" \
  ralph-env \
  python ralph.py --prompt-file todo_api.md \
    --completion-promise "COMPLETE" --max-iterations 30
```

## Container Configuration Options

### Network Modes

**Option 1: No Network (Most Secure)**

Prevents Ralph from making external network requests:

```bash
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  --network=none \
  ralph-env \
  python ralph.py --prompt-file prompt.md --completion-promise "COMPLETE"
```

⚠️ **Limitation:** Ralph cannot install packages with pip/npm or make API calls (except to LLM).

**Option 2: With Network (Default)**

Allows Ralph to install packages and make requests:

```bash
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  ralph-env \
  python ralph.py --prompt-file prompt.md --completion-promise "COMPLETE"
```

Use this when Ralph needs to `pip install` dependencies.

### Resource Limits

Adjust based on your system and task complexity:

```bash
# Light tasks (simple scripts)
--memory="1g" --cpus="1"

# Medium tasks (REST API with tests)
--memory="2g" --cpus="2"

# Heavy tasks (complex applications)
--memory="4g" --cpus="4"

# Prevent process fork bombs
--pids-limit=100
```

### Read-Only Mode (Extra Safe)

Test prompts without any file modifications:

```bash
# Add PATCHPAL_READ_ONLY to .env.ralph temporarily
echo "PATCHPAL_READ_ONLY=true" >> .env.ralph

# Run Ralph in read-only mode
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  ralph-env \
  python ralph.py --prompt-file prompt.md \
    --completion-promise "COMPLETE" --max-iterations 5

# Remove read-only flag when ready for real run
sed -i '/PATCHPAL_READ_ONLY/d' .env.ralph
```

## Advanced Patterns

### Overnight/Background Runs

Run Ralph in detached mode overnight:

```bash
# Start Ralph in background
podman run -d \
  --name ralph-overnight \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  --memory="4g" --cpus="4" \
  ralph-env \
  python ralph.py --prompt-file big_task.md \
    --completion-promise "COMPLETE" --max-iterations 100 \
  > ralph_session.log 2>&1

# Check progress
podman logs -f ralph-overnight

# Check if still running
podman ps | grep ralph-overnight

# Stop if needed
podman stop ralph-overnight

# View results in the morning
cat ralph_session.log
git diff
```

### Multiple Parallel Ralph Instances

Run multiple Ralph instances on different tasks:

```bash
# Terminal 1: Feature A
cd ~/ralph-sandbox/feature-a
podman run -it --rm \
  --name ralph-feature-a \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  ralph-env \
  python ralph.py --prompt-file feature_a.md --completion-promise "DONE"

# Terminal 2: Feature B (simultaneously!)
cd ~/ralph-sandbox/feature-b
podman run -it --rm \
  --name ralph-feature-b \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  ralph-env \
  python ralph.py --prompt-file feature_b.md --completion-promise "DONE"
```

### Using Local Models (Zero Cost)

If you have a local LLM running (Ollama, vLLM, LM Studio):

```bash
# Update .env.ralph
cat > .env.ralph <<'EOF'
PATCHPAL_MODEL=hosted_vllm/openai/qwen2.5-coder-32b-instruct
HOSTED_VLLM_API_BASE=http://host.containers.internal:8000
HOSTED_VLLM_API_KEY=dummy-key
PATCHPAL_REQUIRE_PERMISSION=false
EOF

# Run Ralph with local model (zero API cost!)
podman run -it --rm \
  -v $(pwd):/workspace:Z \
  --env-file .env.ralph \
  ralph-env \
  python ralph.py --prompt-file prompt.md --completion-promise "COMPLETE"
```

**Note:** `host.containers.internal` allows container to access services on host machine.

## Safety Checklist

Before running Ralph with Podman, verify:

- [ ] Running in isolated directory (`~/ralph-sandbox`)
- [ ] Git initialized (can rollback with `git reset --hard`)
- [ ] Using Podman container (isolated from host)
- [ ] Resource limits set (`--memory`, `--cpus`)
- [ ] No important data in workspace
- [ ] API key is set in `.env.ralph`
- [ ] Low `max-iterations` for first test (5-10)
- [ ] Can easily delete entire sandbox directory
- [ ] `.env.ralph` added to `.gitignore`
- [ ] Network isolation considered (use `--network=none` if possible)

## Troubleshooting

### Problem: WSL cgroup warnings

```bash
# Warning: The cgroupv2 manager is set to systemd but there is no systemd user session available

# Solution: Add --cgroup-manager=cgroupfs to all podman commands
podman build --cgroup-manager=cgroupfs -f Dockerfile.ralph -t ralph-env .
podman run --cgroup-manager=cgroupfs -it --rm -v $(pwd):/workspace:Z ...
```

### Problem: Permission denied with volume mount

```bash
# Error: Permission denied accessing /workspace

# Solution: Add :Z flag for SELinux contexts
-v $(pwd):/workspace:Z
```

### Problem: Container can't reach host services

```bash
# Error: Cannot connect to http://localhost:8000

# Solution: Use host.containers.internal
HOSTED_VLLM_API_BASE=http://host.containers.internal:8000
```

### Problem: ralph.py not found

```bash
# Error: python: can't open file 'ralph.py'

# Solution: Copy script to sandbox directory
cp /path/to/patchpal/examples/ralph/ralph.py ~/ralph-sandbox/
```

### Problem: API key not working

```bash
# Error: ANTHROPIC_API_KEY not set or invalid

# Solution: Verify .env.ralph contains valid key
cat .env.ralph  # Check file contents
# Make sure no extra spaces or quotes around key
```

### Problem: Out of memory

```bash
# Error: Container killed (OOM)

# Solution: Increase memory limit
--memory="4g"  # or higher

# Or reduce max-iterations to limit context growth
--max-iterations 20
```

### Problem: Ralph never completes

```bash
# Ralph reaches max-iterations without completion

# Solution: Review prompt - make success criteria clearer
# Check if completion promise is too generic
# Increase max-iterations if making progress
# Add escape hatches in prompt
```

### Problem: Want to inspect container while running

```bash
# Open shell in running container
podman exec -it ralph-test /bin/bash

# Check files Ralph is creating
ls -lah /workspace

# Exit without stopping Ralph
exit
```

## Cleaning Up

### Remove Containers

```bash
# List all containers
podman ps -a

# Remove stopped containers
podman rm ralph-test

# Force remove running container
podman rm -f ralph-overnight
```

### Remove Images

```bash
# List images
podman images

# Remove Ralph image
podman rmi ralph-env

# Remove dangling images
podman image prune
```

### Clean Workspace

```bash
# Reset git to clean state
cd ~/ralph-sandbox
git reset --hard HEAD
git clean -fd

# Or delete entire sandbox
cd ~
rm -rf ~/ralph-sandbox
```

## Next Steps

Once comfortable with Podman Ralph:

1. **Try complex prompts** - Build multi-file applications
2. **Experiment with iterations** - Find the sweet spot for your tasks
3. **Use multi-phase builds** - Break large projects into phases
4. **Monitor costs** - Track token usage and optimize
5. **Share prompts** - Document what works for your use cases

## Comparison: Podman vs Docker

Both work identically for Ralph. Main differences:

| Feature | Podman | Docker |
|---------|--------|--------|
| Root required | No (rootless) | Yes (daemon) |
| Daemon | No | Yes |
| Systemd integration | Better | Worse |
| CLI compatibility | docker-compatible | Standard |
| Security model | Rootless by default | Root by default |

Replace `podman` with `docker` in all commands and they work the same.

## Additional Resources

- **Podman Documentation**: https://docs.podman.io/
- **Ralph Main README**: [`./README.md`](./README.md)
- **Example Prompts**: [`./prompts/`](./prompts/)
- **Multi-Phase Example**: [`./multi_phase_ralph.py`](./multi_phase_ralph.py)

## Contributing

Found issues or improvements for the Podman setup? PRs welcome!
