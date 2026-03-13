# Using Local Models (vLLM & Ollama)

Run models locally on your machine without needing API keys or internet access.

**⚠️ IMPORTANT: For local models, we recommend vLLM.**

vLLM provides:
- ✅ Robust multi-turn tool calling
- ✅ 3-10x faster inference than Ollama
- ✅ Production-ready reliability

**For models without native function calling support**, PatchPal includes a [ReAct agent mode](#react-mode-for-models-without-function-calling) that uses text-based tool invocation instead of native function calling APIs.

## vLLM (Recommended for Local Models)

vLLM is significantly faster than Ollama due to optimized inference with continuous batching and PagedAttention.

**Important:** vLLM >= 0.10.2 is required for proper tool calling support.

**Using Local vLLM Server:**

```bash
# 1. Install vLLM (>= 0.10.2)
pip install vllm

# 2. Start vLLM server with tool calling enabled
vllm serve openai/gpt-oss-120b \
  --dtype auto \
  --api-key token-abc123 \
  --tool-call-parser openai \
  --enable-auto-tool-choice

# 3. Use with PatchPal (in another terminal)
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-120b
```

**Using Remote/Hosted vLLM Server:**

```bash
# For remote vLLM servers (e.g., hosted by your organization)
export HOSTED_VLLM_API_BASE=https://your-vllm-server.com
export HOSTED_VLLM_API_KEY=your_api_key_here
patchpal --model hosted_vllm/openai/gpt-oss-120b
```

**Environment Variables:**
- Use `HOSTED_VLLM_API_BASE` and `HOSTED_VLLM_API_KEY`

**Using YAML Configuration (Alternative):**

Create a `config.yaml`:
```yaml
host: "0.0.0.0"
port: 8000
api-key: "token-abc123"
tool-call-parser: "openai"  # Use appropriate parser for your model
enable-auto-tool-choice: true
dtype: "auto"
```

Then start vLLM:
```bash
vllm serve openai/gpt-oss-120b --config config.yaml

# Use with PatchPal
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-120b
```

**Recommended models for vLLM:**
- `openai/gpt-oss-120b` - OpenAI's open-source model (use parser: `openai`)

**Tool Call Parser Reference:**
Different models require different parsers. Common parsers include: `qwen3_xml`, `openai`, `deepseek_v3`, `llama3_json`, `mistral`, `hermes`, `pythonic`, `xlam`. See [vLLM Tool Calling docs](https://docs.vllm.ai/en/latest/features/tool_calling/) for the complete list.

## Ollama

Ollama v0.14+ supports tool calling for agentic workflows. However, proper configuration is **critical** for reliable operation.

**Requirements:**

1. **Ollama v0.14.0 or later** - Required for tool calling support
2. **Sufficient context window** - Default 4096 tokens is too small; increase to at least 32K

**Recommended Settings for Local Models:**

For better performance with local models (both Ollama and vLLM), especially smaller models (<20B params):

```bash
# Reduce tool confusion by limiting to 5 essential tools
export PATCHPAL_MINIMAL_TOOLS=true

# Disable web tools for offline/faster operation
export PATCHPAL_ENABLE_WEB=false

# Disable streaming (fixes Ollama tool call bug - see openclaw/openclaw#5769)
export PATCHPAL_STREAM_OUTPUT=false

# Use with Ollama
patchpal --model ollama_chat/glm-4.7-flash:q4_K_M
```

**Benefits:**
- **Fewer tools** - Reduces tool confusion with smaller models
- **Fixes tool calls** - Ollama's streaming drops tool calls; disabling fixes this

**Setup Instructions:**

**For Native Ollama Installation:**

```bash
# Set context window size (required!)
export OLLAMA_CONTEXT_LENGTH=32768

# Start Ollama server
ollama serve

# In another terminal, use with PatchPal
patchpal --model ollama_chat/gpt-oss:120b
```

**For Docker:**

```bash
# Stop existing container (if running)
docker stop ollama
docker rm ollama

# Start with proper configuration
docker run -d \
  --gpus all \
  -e OLLAMA_CONTEXT_LENGTH=32768 \
  -v ollama:/root/.ollama \
  -p 11434:11434 \
  --name ollama \
  ollama/ollama

# Verify configuration
docker exec -it ollama ollama run gpt-oss:120b
# In the Ollama prompt, type: /show parameters
# Should show num_ctx much larger than default 4096

# Use with PatchPal
patchpal --model ollama_chat/glm-4.7-flash:q4_K_M
```

**Verifying Context Window Size:**

```bash
# Check your Ollama container configuration
docker inspect ollama | grep OLLAMA_CONTEXT_LENGTH

# Or run a model and check parameters
docker exec -it ollama ollama run glm-4.7-flash:q4_K_M
>>> /show parameters
```

**Recommended Models for Tool Calling:**

- `gpt-oss:120b` - OpenAI's open-source model
- `glm-4.7-flash:q4_K_M` - Z.ai's GLM model, excellent tool calling
- `qwen3:32b` - Qwen3 model with good agentic capabilities
- `qwen3-coder` - Specialized for coding tasks

**Performance Note:**

While Ollama now works with proper configuration, vLLM is still recommended for production use due to:
- 3-10x faster inference
- More robust tool calling implementation
- Better memory management

**Examples:**

```bash
# Ollama (works with proper configuration)
export OLLAMA_CONTEXT_LENGTH=32768
patchpal --model ollama_chat/qwen3:32b
patchpal --model ollama_chat/gpt-oss:120b
patchpal --model ollama_chat/glm-4.7-flash:q4_K_M

# vLLM (recommended for production)
patchpal --model hosted_vllm/openai/gpt-oss-120b
```

## ReAct Mode for Models Without Function Calling

Some local models (especially smaller ones) struggle with native function calling. For these models, PatchPal provides a **ReAct (Reason + Act)** agent mode that uses text-based tool invocation instead of function calling APIs.

**Why ReAct Mode?** Many smaller local models (<20B parameters) either don't support native function calling or perform poorly with it. Even models that technically support function calling may generate malformed JSON, skip required parameters, or fail to invoke tools reliably. ReAct mode sidesteps these issues by using simple text-based patterns that are easier for such models to follow.

### What is ReAct?

ReAct is a prompting pattern where the LLM follows this loop:

1. **Thought**: Reason about what needs to be done
2. **Action**: Invoke a tool with parameters (formatted as text/JSON)
3. **PAUSE**: Wait for the tool result
4. **Observation**: Receive the tool's output
5. **Repeat** or output final **Answer**

Instead of using native function calling APIs, the agent parses tool invocations from the model's text output.

### When to Use ReAct Mode

Use ReAct mode when:
- Your model doesn't support native function calling
- Native function calling is unreliable for your model
- You're using smaller models (<20B parameters) that struggle with function calling
- You want text-based tool invocation for debugging/transparency

### Available Tools

ReAct mode includes these tools by default:

- `read_file` - Read file contents
- `read_lines` - Read specific lines from a file
- `write_file` - Create or overwrite files
- `edit_file` - Find and replace in files
- `run_shell` - Execute shell commands
- `grep` - Search for patterns in files
- `list_files` - List directory contents
- `web_search` - Search the web
- `web_fetch` - Fetch webpage content

You can limit tools if needed:

```python
agent = create_react_agent(
    model_id="ollama_chat/your_model",
    enabled_tools=["read_file", "write_file", "edit_file"]
)
```

### Enabling ReAct Mode

**CLI:**
```bash
# Use ReAct mode with any model
export PATCHPAL_REACT_MODE=true
patchpal --model ollama_chat/llama3.2

# Or inline
PATCHPAL_REACT_MODE=true patchpal --model ollama_chat/qwen2.5

# Limit tools using environment variable
export PATCHPAL_REACT_MODE=true
export PATCHPAL_ENABLED_TOOLS="read_file,write_file,edit_file"
patchpal --model ollama_chat/llama3.2
```

**Python API:**
```python
from patchpal import create_react_agent

# Basic usage
agent = create_react_agent(model_id="ollama_chat/llama3.2")
response = agent.run("List the Python files")
print(response)

# With custom tools
def calculator(x: int, y: int) -> str:
    """Add two numbers together."""
    return str(x + y)

agent = create_react_agent(
    model_id="ollama_chat/qwen2.5",
    custom_tools=[calculator]
)
response = agent.run("What is 42 plus 58?")
```

### Recommended Models for ReAct

These Ollama models work well with ReAct mode:
- **`qwen2.5:7b`** ⭐ - Excellent instruction following
- **`llama3.1:8b`** ⭐ - Good reliability
- **`llama3.2:3b`** - Fast, good for simple tasks
- **`deepseek-coder-v2`** - Great for code tasks
- **`mistral:7b`** - Solid general-purpose

### Best Practices

1. **Start with defaults** - These tools are available by default:
   ```bash
   PATCHPAL_REACT_MODE=true patchpal --model ollama_chat/llama3.1:8b
   ```

2. **Limit tools for simpler tasks** - Fewer tools can improve focus:
   ```python
   agent = create_react_agent(
       model_id="ollama_chat/your_model",
       enabled_tools=["read_file", "write_file", "edit_file"]
   )
   ```

3. **Add custom instructions** - Guide the model's behavior:
   ```python
   agent = create_react_agent(
       model_id="ollama_chat/your_model",
       custom_instructions="""
       - Answer general questions directly without tools
       - Only use tools for file/code operations
       - Provide concise answers
       """
   )
   ```

### Native Function Calling vs ReAct

| Aspect | Native Function Calling | ReAct Mode |
|--------|------------------------|------------|
| **Model Support** | Requires function calling | Works with any LLM |
| **Reliability** | High (API-enforced) | Good (prompt-based) |
| **Performance** | Generally faster | Comparable |
| **Setup** | Zero config (if supported) | Single env var |
| **Parallel Tools** | Supported | Sequential only |
| **Debugging** | Opaque API calls | Visible text reasoning |

### Troubleshooting ReAct Mode

**Model not following format:**
- Try a better/larger model
- Simplify the task into smaller steps
- Add more explicit instructions via `custom_instructions`

**Tool calls not being parsed:**
Ensure model outputs exact format:
```
Action: tool_name: {"param": "value"}
PAUSE
```

**Agent looping without finishing:**
- Reduce `max_iterations` to fail faster
- Try a model that better understands completion signals
- Add explicit completion instructions

### Implementation Details

- Source code: [`patchpal/agent/react.py`](https://github.com/amaiya/patchpal/blob/main/patchpal/agent/react.py)
- Example: [`examples/react_agent_example.py`](https://github.com/amaiya/patchpal/blob/main/examples/react_agent_example.py)
- Based on [Simon Willison's ReAct pattern](https://til.simonwillison.net/llms/python-react-pattern) and [smolagents](https://github.com/huggingface/smolagents)
- Academic paper: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
