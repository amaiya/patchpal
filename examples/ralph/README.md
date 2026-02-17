# Ralph Wiggum Technique for PatchPal

> "I'm learnding!" - Ralph Wiggum

The **Ralph Wiggum technique** is an iterative AI development methodology where an agent repeatedly works on a task until completion. This technique is implemented as **autopilot mode** in PatchPal.

## Documentation

For complete documentation on using autopilot mode, see:

**[docs/usage/autopilot.md](../../docs/usage/autopilot.md)**

The documentation covers:
- Quick start and usage
- How it works (stop hook mechanism)
- Writing effective prompts
- Safety considerations and sandboxing
- Python library usage
- Best practices

## Examples in This Directory

```
examples/ralph/
├── README.md                           # This file
├── ralph.py                            # Standalone, modifiable script for running Ralph Wiggum method
├── simple_autopilot_example.py         # Simple example using autopilot as Python library
├── multi_phase_todo_api_example.py     # Multi-phase example (sequential phases)
└── prompts/                            # Example prompt templates
    ├── todo_api.md                     # Build a REST API
    ├── fix_tests.md                    # Fix failing tests
    └── refactor.md                     # Refactor code
```

## Learn More

- **PatchPal Autopilot Documentation**: [docs/usage/autopilot.md](../../docs/usage/autopilot.md)
- **Ralph Technique Origins**:
  - [Ralph Wiggum as a "Software Engineer"](https://ghuntley.com/ralph/) - Geoffrey Huntley's comprehensive guide
  - [A Brief History of Ralph](https://www.humanlayer.dev/blog/brief-history-of-ralph)
  - [Ralph Wiggum - Awesome Claude](https://awesomeclaude.ai/ralph-wiggum)
