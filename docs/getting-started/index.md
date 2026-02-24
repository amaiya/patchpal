# Getting Started

## Installation

Install PatchPal from PyPI:

```bash
pip install patchpal
```

**Supported Operating Systems:**  Linux, MacOS, MS Windows.

## Setup

1. **Get an API key or a Local LLM Engine**:
   - **[Cloud]** For Anthropic models (default): Sign up at https://console.anthropic.com/
   - **[Cloud]** For OpenAI models: Get a key from https://platform.openai.com/
   - **[Local]** For vLLM: Install from https://docs.vllm.ai/ (free - no API charges) **Recommended for Local Use**
   - **[Local]** For Ollama: Install from https://ollama.com/ (⚠️ requires `OLLAMA_CONTEXT_LENGTH=32768` - see Ollama section below)
   - For other providers: Check the [LiteLLM documentation](https://docs.litellm.ai/docs/providers)

2. **Set up your API key as environment variable**:
```bash

# For Anthropic (default)
export ANTHROPIC_API_KEY=your_api_key_here

# For OpenAI
export OPENAI_API_KEY=your_api_key_here

# For vLLM - API key required only if configured
export HOSTED_VLLM_API_BASE=http://localhost:8000 # depends on your vLLM setup
export HOSTED_VLLM_API_KEY=token-abc123           # optional depending on your vLLM setup

# No API required for Ollama.

# For other providers, check LiteLLM docs
```

3. **Run PatchPal**:
```bash
# Use default model (anthropic/claude-sonnet-4-5)
patchpal

# Use a specific model via command-line argument
patchpal --model openai/gpt-5.2-codex  # or openai/gpt-5-mini, anthropic/claude-opus-4-5, etc.

# Use vLLM (local)
# Note: vLLM server must be started with --tool-call-parser and --enable-auto-tool-choice
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b

# Use Ollama (local - requires OLLAMA_CONTEXT_LENGTH=32768)
export OLLAMA_CONTEXT_LENGTH=32768
patchpal --model ollama_chat/glm-4.7-flash:q4_K_M

# Or set the model via environment variable
export PATCHPAL_MODEL=anthropic/claude-opus-4-5
patchpal
```

**Tip for Local Models:** Local models (i.e., models served by Ollama or vLLM) may work better with the environment variable setting,           `PATCHPAL_MINIMAL_TOOLS=true`, which provides only essential tools (`read_file`, `read_lines`, `edit_file`, `write_file`, `run_shell`), reducing tool        confusion with smaller models.
