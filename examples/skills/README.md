# Skills Examples

This directory contains example skills that demonstrate how to create reusable workflows for PatchPal.

## What Are Skills?

Skills are prompt-based workflows defined as markdown files that guide the agent through specific tasks. Unlike custom tools (which execute Python code), skills provide instructions that the agent follows.

## Quick Start

**1. Copy a skill to your personal directory:**
```bash
cp -r commit ~/.patchpal/skills/
```

**2. Start PatchPal and invoke the skill:**
```bash
patchpal

You: /commit Fix authentication bug
# Agent follows the commit skill's instructions
```

**3. Or use natural language:**
```bash
You: Help me create a good commit message
# Agent automatically discovers and uses the commit skill
```

## Available Example Skills

### PatchPal-Created Skills

**commit** - Best practices for creating git commits
- Proper formatting and structure
- Conventional commit standards
- Clear, descriptive messages

**review** - Comprehensive code review checklist
- Security considerations
- Performance review
- Code quality checks
- Documentation review

**add-tests** - Add comprehensive pytest tests
- Includes code block templates
- Test structure examples
- Coverage strategies

### From Anthropic's Official Skills Repository

**slack-gif-creator** - Create animated GIFs optimized for Slack
- Source: https://github.com/anthropics/skills
- License: Apache 2.0 (see ATTRIBUTION.md)
- Demonstrates Claude Code skill compatibility

**skill-creator** - Guide for creating effective skills
- Source: https://github.com/anthropics/skills/tree/main/skills/skill-creator
- License: Apache 2.0 (see ATTRIBUTION.md)
- Includes bundled scripts: `init_skill.py`, `package_skill.py`, `quick_validate.py`
- Demonstrates full bundled resources support

## Installation

**Personal skills (available in all projects):**
```bash
# Copy all example skills
cp -r examples/skills/* ~/.patchpal/skills/

# Or copy individual skills
cp -r examples/skills/commit ~/.patchpal/skills/
cp -r examples/skills/review ~/.patchpal/skills/
cp -r examples/skills/add-tests ~/.patchpal/skills/
```

**Project-specific skills (only in this repository):**
```bash
mkdir -p .patchpal/skills
cp -r examples/skills/commit .patchpal/skills/
```

## Skill File Format

Skills are markdown files with YAML frontmatter:

```markdown
---
name: my-skill
description: Brief description of what this skill does
---
# Instructions

Your detailed step-by-step instructions here...

## Step 1: Analyze
- Check this
- Verify that

## Step 2: Execute
- Do this
- Then that

## Step 3: Validate
- Confirm results
- Check for issues
```

**Required fields:**
- `name` - Skill identifier (used with `/skillname`)
- `description` - One-line summary (shown in skill list)

**Instructions section:**
- Step-by-step guidance for the agent
- Can reference PatchPal tools: `read_file`, `git_status`, etc.
- Can include code templates and examples
- Markdown formatting supported

## Creating Your Own Skills

**1. Create the skill directory:**
```bash
mkdir -p ~/.patchpal/skills/my-skill
```

**2. Create SKILL.md:**
```bash
cat > ~/.patchpal/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: What your skill does
---
# Instructions

Step-by-step instructions...
EOF
```

**3. Use your skill:**
```bash
patchpal

You: /my-skill
# Or just describe what you want
You: I need help with [skill purpose]
```

## Skill Invocation

**Two ways to invoke skills:**

**1. Direct invocation (explicit):**
```bash
You: /commit Fix authentication bug
You: /review Check security of auth.py
```

**2. Natural language (automatic discovery):**
```bash
You: Help me create a commit message
You: Please review this code for issues
```

## Finding Available Skills

Ask the agent to list them:
```bash
You: list skills
```

Or check your directories:
```bash
ls ~/.patchpal/skills/       # Personal skills
ls .patchpal/skills/          # Project-specific skills
```

## Skill Priority

- Project skills (`.patchpal/skills/`) override personal skills
- If both locations have a skill with the same name, project version is used

## Best Practices

**Keep skills focused:**
- One clear purpose per skill
- Break complex workflows into multiple skills

**Use clear instructions:**
- Step-by-step guidance
- Specific tool calls when needed
- Include examples and templates

**Reference PatchPal tools:**
```markdown
1. Use `git_status` to check current changes
2. Use `read_file` to review modified files
3. Use `git_diff` to see the changes
```

**Include code templates:**
````markdown
Use this test template:

```python
def test_function():
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```
````

## Real-World Skill Ideas

**Documentation generator:**
```markdown
---
name: document
description: Generate documentation for code
---
# Instructions
1. Read the source file
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
1. Check tests pass: `run_shell pytest`
2. Verify git status is clean
3. Review CHANGELOG.md
4. Confirm version bump
5. Check CI/CD pipeline status
```

## Bundled Resources

Skills can include additional files:

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

## Learn More

- **Main Documentation**: See main README.md "Skills System" section
- **Skills Discovery**: `patchpal/skills.py`
- **Anthropic's Skills**: https://github.com/anthropics/skills

## Differences: Skills vs. Custom Tools

| Feature | Skills | Custom Tools |
|---------|--------|--------------|
| **Type** | Markdown instructions | Python functions |
| **Purpose** | Guide agent through workflow | Execute code |
| **Location** | `~/.patchpal/skills/` or `.patchpal/skills/` | `~/.patchpal/tools/` only |
| **Invocation** | `/skillname` or natural language | Automatic (when relevant) |
| **Execution** | Agent follows instructions | Python code runs |
| **Best For** | Complex workflows, checklists | Calculations, API calls, data processing |

Choose skills for guiding the agent through processes, choose custom tools for executing specific code operations!
