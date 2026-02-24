# PatchPal — An Agentic Coding and Automation Assistant

<img src="https://raw.githubusercontent.com/amaiya/patchpal/refs/heads/main/assets/patchpal_screenshot.png" alt="PatchPal Screenshot" width="650"/>

> Supporting both local and cloud LLMs, with autopilot mode and extensible tools.

[**PatchPal**](https://github.com/amaiya/patchpal) is an AI coding agent that helps you build software, debug issues, and automate tasks. It supports agent skills, tool use, and executable Python generation, enabling interactive workflows for tasks such as data analysis, visualization, web scraping, API interactions, and research with synthesized findings.

Most agent frameworks are [built in TypeScript](https://news.ycombinator.com/item?id=44212560). PatchPal is Python-native, designed for developers who want both interactive terminal use (`patchpal`) and programmatic API access (`agent.run("task")`) in the same tool—without switching ecosystems.

**Key Features**

- [Terminal Interface](usage/interactive.md) for interactive development
- [Python SDK](usage/python-api.md) for flexibility and extensibility
- [Built-In](features/tools.md) and [Custom Tools](features/custom-tools.md)
- [Skills System](features/skills.md)
- [Autopilot Mode](usage/autopilot.md) using [Ralph Wiggum loops](https://ghuntley.com/ralph/)
- [Project Memory](features/memory.md) automatically loads project context from `~/.patchpal/repos/<repo-name>/MEMORY.md` at startup.

PatchPal prioritizes customizability: custom tools, custom skills, a flexible Python API, and support for any tool-calling LLM.

## Quick Start

```bash
$ pip install patchpal  # install
$ patchpal              # start
```

> Platform support: Linux, macOS, and Windows are all supported

## Beyond Coding: General Problem-Solving

While originally designed for software development, PatchPal is also a general-      purpose assistant. With web search, file operations, shell commands, and custom      tools/skills, it can help with research, data analysis, document processing, log     file analyses, etc.

<img src="https://raw.githubusercontent.com/amaiya/patchpal/refs/heads/main/assets/patchpal_assistant.png" alt="PatchPal as General Assistant" width="650"/>
