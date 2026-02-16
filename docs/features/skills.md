# Skills System

Skills are reusable workflows and custom commands that can be invoked by name or discovered automatically by the agent.

## Creating Your Own Skills

1. **Choose a location:**
   - Personal skills (all projects): `~/.patchpal/skills/<skill-name>/SKILL.md`
   - Project-specific skills: `<repo>/.patchpal/skills/<skill-name>/SKILL.md`

2. **Create the skill file:**
```bash
# Create a personal skill
mkdir -p ~/.patchpal/skills/my-skill
cat > ~/.patchpal/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: Brief description of what this skill does
---
# Instructions
Your detailed instructions here...
EOF
```

3. **Skill File Format:**
```markdown
---
name: skill-name
description: One-line description
---
# Detailed Instructions
- Step 1: Do this
- Step 2: Do that
- Use specific PatchPal tools like git_status, read_file, etc.
```

## Example Skills

The PatchPal repository includes [example skills](https://github.com/amaiya/patchpal/tree/main/examples/skills) you can use as templates:

### PatchPal-Created Skills

- **commit** - Best practices for creating git commits with proper formatting and conventional commit standards
- **review** - Comprehensive code review checklist covering security, performance, code quality, and documentation
- **add-tests** - Add comprehensive pytest tests (includes code block templates and test structure examples)

### From Anthropic's Official Skills Repository

- **slack-gif-creator** - Create animated GIFs optimized for Slack (from [Anthropic's official skills repo](https://github.com/anthropics/skills), demonstrates Claude Code compatibility)
- **skill-creator** - Guide for creating effective skills with bundled scripts and references (from [Anthropic's official skills repo](https://github.com/anthropics/skills/tree/main/skills/skill-creator), demonstrates full bundled resources support)

**After `pip install patchpal`, get examples:**

```bash
# Quick way: Download examples directly from GitHub
curl -L https://github.com/amaiya/patchpal/archive/main.tar.gz | tar xz --strip=1 patchpal-main/examples

# Or clone the repository
git clone https://github.com/amaiya/patchpal.git
cd patchpal

# Copy examples to your personal skills directory
cp -r examples/skills/commit ~/.patchpal/skills/
cp -r examples/skills/review ~/.patchpal/skills/
cp -r examples/skills/add-tests ~/.patchpal/skills/
cp -r examples/skills/skill-creator ~/.patchpal/skills/
```

**View examples online:**
Browse the [examples/skills/](https://github.com/amaiya/patchpal/tree/main/examples/skills) directory on GitHub to see the skill format and create your own.

You can also try out the example skills at [anthropic/skills](https://github.com/anthropics/skills).


## Using Skills

There are two ways to invoke skills:

1. **Direct invocation** - Type `/skillname` at the prompt:
```bash
$ patchpal
You: /commit Fix authentication bug
```

2. **Natural language** - Just ask, and the agent discovers the right skill:
```bash
You: Help me commit these changes following best practices
# Agent automatically discovers and uses the commit skill
```

## Finding Available Skills

Ask the agent to list them:
```bash
You: list skills
```

## Skill Priority

Project skills (`.patchpal/skills/`) override personal skills (`~/.patchpal/skills/`) with the same name.

## Bundled Resources

Skills can include additional files alongside the main `SKILL.md`:

```
~/.patchpal/skills/my-skill/
├── SKILL.md              # Main skill file (required)
├── template.py           # Code template
├── checklist.md          # Reference document
└── scripts/              # Helper scripts
    └── validate.py
```

Reference bundled files in your skill:
```markdown
Use the template in `template.py` as a starting point.
Run `python scripts/validate.py` to check results.
```

The `skill-creator` example demonstrates full bundled resources support with scripts and reference documents.

## Real-World Skill Ideas

**Documentation generator:**
```markdown
---
name: document
description: Generate documentation for code
---
# Instructions
1. Read the source file with `read_file`
2. Analyze functions and classes
3. Generate docstrings following project style
4. Add usage examples
```

**Refactoring assistant:**
```markdown
---
name: refactor
description: Refactor code following best practices
---
# Instructions
1. Analyze current code structure
2. Identify code smells
3. Suggest improvements
4. Apply changes with user approval
```

**Deployment checklist:**
```markdown
---
name: deploy
description: Pre-deployment checklist
---
# Instructions
1. Check tests pass: `run_shell("pytest")`
2. Verify git status is clean with `git_status`
3. Review CHANGELOG.md
4. Confirm version bump
5. Check CI/CD pipeline status
```

## Skills vs. Custom Tools

| Feature | Skills | Custom Tools |
|---------|--------|--------------|
| **Type** | Markdown instructions | Python functions |
| **Purpose** | Guide agent through workflow | Execute code |
| **Location** | `~/.patchpal/skills/` or `.patchpal/skills/` | `~/.patchpal/tools/` or `.patchpal/tools/` |
| **Invocation** | `/skillname` or natural language | Automatic (when relevant) |
| **Execution** | Agent follows instructions | Python code runs |
| **Best For** | Complex workflows, checklists | Calculations, API calls, data processing |

Choose skills for guiding the agent through processes, choose custom tools for executing specific code operations!
