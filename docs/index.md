# PatchPal — An Agentic Coding and Automation Assistant

<img src="https://raw.githubusercontent.com/wiseprobe/patchpal/refs/heads/main/assets/patchpal_screenshot.png" alt="PatchPal Screenshot" width="650"/>

> Supporting both local and cloud LLMs, with autopilot mode and extensible tools.

[**PatchPal**](https://github.com/wiseprobe/patchpal) is an AI coding agent that helps you build software, debug issues, and automate tasks. It supports agent skills, tool use, and executable Python generation, enabling interactive workflows for tasks such as data analysis, visualization, web scraping, API interactions, and research with synthesized findings.

**Key Features**

- [Terminal Interface](usage/interactive.md) for interactive development
- [Python API](usage/python-api.md) for flexibility and extensibility
- [Built-In](features/tools.md) and [Custom Tools](features/custom-tools.md)
- [Skills System](features/skills.md)
- [Autopilot Mode](usage/autopilot.md) using [Ralph Wiggum loops](https://ghuntley.com/ralph/)
- [Project Memory](features/memory.md) automatically loads project context from `~/.patchpal/<repo-name>/MEMORY.md` at startup.

A key goal of this project is to remain lean, accessible, and configurable, enabling learning, experimentation, and broad applicability across use cases.


## Quick Start

```bash
$ pip install patchpal  # install
$ patchpal              # start
```

## Beyond Coding: General Problem-Solving

While PatchPal excels at software development tasks, it's also a general-purpose assistant. With access to web search, file operations, and shell commands, PatchPal can help with research, data analysis, document processing, and more.

<img src="https://raw.githubusercontent.com/wiseprobe/patchpal/refs/heads/main/assets/patchpal_assistant.png" alt="PatchPal as General Assistant" width="650"/>
