# patchpal-simple

A minimal CLI for small local Ollama models, using text-based tool calling instead of structured function calling.

## Overview

`patchpal-simple` is optimized for local models that struggle with structured function calling (like Qwen2.5-coder and similar models). It uses a simplified approach inspired by [Peen](https://github.com/codazoda/peen):

- **Text-based tool parsing** - Models generate simple JSON in plain text rather than using structured function calling
- **Two tools only** - `run` (shell commands) and `write` (file operations)
- **Automatic planning** - Breaks down complex tasks into TODO lists
- **Repair prompts** - Helps models fix malformed tool calls
- **Minimal context** - Simple prompts that don't overwhelm small models

## Why patchpal-simple?

Popular AI coding tools use structured function calling (XML for Anthropic, JSON schemas for OpenAI). Many local models struggle with these formats because:

1. They weren't extensively trained on structured tool calling formats
2. Tool schemas are verbose and consume significant context
3. The format is more complex than learning from plain text examples

`patchpal-simple` solves this by using simple JSON tool calls that models learn from examples:

```json
{"tool":"run","cmd":"ls -la"}
{"tool":"write","path":"hello.py","content":"print('Hello')"}
```

## Installation

`patchpal-simple` is included with PatchPal:

```bash
pip install patchpal
```

## Usage

### Basic Usage

```bash
# Interactive mode
patchpal-simple

# One-shot command
patchpal-simple "create a hello world script in Python"
```

### Configuration

Set via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PATCHPAL_SIMPLE_HOST` | `http://127.0.0.1:11434` | Ollama server URL |
| `PATCHPAL_SIMPLE_MODEL` | `qwen2.5-coder:7b` | Model to use |

Or use command-line arguments:

```bash
# Specify model
patchpal-simple --model qwen2.5-coder:14b

# Custom Ollama host
patchpal-simple --host http://192.168.1.100:11434

# Custom working directory
patchpal-simple --root /path/to/project
```

## Recommended Models

Local models that work well with patchpal-simple:

- **qwen2.5-coder:7b** - Good balance of size and capability
- **qwen2.5-coder:14b** - More capable, requires more RAM
- **qwen2.5-coder:3b** - Fastest, more limited capability
- **codellama:7b** - Meta's code model

The key is using models that struggle with structured function calling but can follow JSON examples. Parameter count matters less than training data.

Pull a model:

```bash
ollama pull qwen2.5-coder:7b
```

## How It Works

### 1. Planning Phase

When you give a request, patchpal-simple first creates a TODO list:

```
User: "Create a Flask hello world app"

🤔 Planning...
TODO:
- [ ] Create app.py with Flask hello world
- [ ] Create requirements.txt with Flask dependency
- [ ] Test the app runs
```

### 2. Execution Phase

Then it executes steps one at a time:

```
🤔 Thinking...
I'll create the Flask app file.
{"tool":"write","path":"app.py","content":"from flask import Flask\n\napp = Flask(__name__)\n\n@app.route('/')\ndef hello():\n    return 'Hello, World!'\n\nif __name__ == '__main__':\n    app.run()"}

write: app.py
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'...
```

### 3. Verification

After each step, the model verifies the operation succeeded before continuing.

## Tool Format

Models use simple one-line JSON:

### run - Execute shell commands

```json
{"tool":"run","cmd":"cat file.txt"}
{"tool":"run","cmd":"ls -la && pwd"}
```

### write - Create or overwrite files

```json
{"tool":"write","path":"hello.py","content":"print('Hello')"}
{"tool":"write","path":"src/app.js","content":"const x = 1;\nconsole.log(x);"}
```

**Important**: Use `\n` for newlines (not actual line breaks).

## Examples

### Create a Python Script

```bash
patchpal-simple "create a script that lists all .py files"
```

### Refactor Code

```bash
patchpal-simple "refactor calculate.py to use functions"
```

### Debug an Error

```bash
patchpal-simple "fix the ImportError in main.py"
```

## Comparison: patchpal vs patchpal-simple

| Feature | patchpal | patchpal-simple |
|---------|----------|-----------------|
| **Models** | Large models (Claude, GPT-4, Qwen 32B+) or tool-calling models | Models without strong structured function calling |
| **Tool calling** | Structured (LiteLLM) | Text-based (JSON parsing) |
| **Tools** | 20+ tools (read_file, grep, git_*, etc.) | 2 tools (run, write) |
| **Context management** | Automatic compaction | Simple truncation |
| **Planning** | Optional | Built-in for all requests |
| **Use case** | Professional development | Quick scripts, learning, resource-constrained environments |

## Limitations

- **Two tools only** - Complex operations require multiple steps
- **No git integration** - Use `run` tool with git commands
- **No web access** - Local-only operations
- **Limited context** - No automatic summarization
- **Ollama only** - Doesn't support cloud APIs

For professional development with larger models, use `patchpal` instead.

## Tips

1. **Be specific** - Models work best with clear, concrete requests
2. **One task at a time** - Break large changes into separate requests
3. **Review output** - These models are more error-prone than frontier models
4. **Use verification** - Models automatically verify write operations
5. **Try different models** - If one doesn't work well, another might succeed

## Troubleshooting

### Model keeps generating invalid JSON

The model might not be compatible. Try:

- Using a different model (qwen2.5-coder recommended)
- Simplifying your request
- Breaking the task into smaller steps

### Model doesn't follow the plan

Models can lose track of multi-step plans. Try:

- Shorter requests (2-3 steps max)
- More specific instructions
- Breaking into separate requests
- Using a different model

### Ollama connection errors

Check that Ollama is running:

```bash
ollama serve
```

Test connection:

```bash
curl http://127.0.0.1:11434/v1/models
```

## Credits

Inspired by [Peen](https://github.com/codazoda/peen) by Joel Dare - a minimal Node.js CLI that pioneered text-based tool calling for small local models.
