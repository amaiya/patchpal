# Project Memory

PatchPal automatically loads project context from a `MEMORY.md` file at startup. Use this file to store project-specific information, technical decisions, conventions, and known issues that persist across sessions. The agent can read and update this file to maintain continuity.

## What to Store in MEMORY.md

- **Project context**: What this project is and what it does
- **Important decisions**: Technical choices and why they were made
- **Key facts**: Deployment info, database details, API endpoints
- **Known issues**: Bugs to fix, technical debt, TODOs
- **Team conventions**: Code style preferences, workflow guidelines

## How It Works

When you start PatchPal, it automatically:
1. Checks for `MEMORY.md` in the repository root (priority)
2. Falls back to `~/.patchpal/repos/<repo-name>/MEMORY.md` if not found
3. Loads the content into the agent's context
4. Makes it available for reference throughout the session

The agent can also read and update MEMORY.md during a session to maintain continuity across multiple sessions.

## Supported Locations

PatchPal supports two locations for `MEMORY.md` with the following priority:

### 1. Repository Root (Priority)
```
<your-repo>/MEMORY.md
```

**Use this location when:**
- You want to share project context with your team
- The memory file should be version controlled
- You want the documentation to travel with the repository

**Advantages:**
- Can be committed to git (`git add MEMORY.md`)
- Shared with all team members
- Easier to edit with your IDE
- Repository-portable

### 2. Home Directory (Default)
```
~/.patchpal/repos/<repo-name>/MEMORY.md
```

**Use this location when:**
- You have personal notes you don't want to share
- The repository is not under your control
- You want to keep PatchPal files separate from your codebase

**Advantages:**
- Kept out of version control by default
- Personal workspace
- Won't pollute repository with tool files
- Works across all your repositories

### Which Location Should You Use?

**For team projects**: Use repository root and commit to version control
```bash
# Create in repo root
echo "# Project Memory\n\n---\n\nOur API uses FastAPI..." > MEMORY.md
git add MEMORY.md
git commit -m "Add project memory"
```

**For personal projects**: Either location works fine (`~/.patchpal/repos/<repo-name>/MEMORY.md` is auto-created if needed)

**For sensitive information**: Use home directory (don't commit to git)

**Important**: Only ONE location is used at a time. If `MEMORY.md` exists in the repository root, that's what PatchPal uses. The home directory version is only checked if there's no repo root file.

## How Priority Works

PatchPal checks locations in this order and uses the **first one it finds**:

1. **Repository root** (`./MEMORY.md`) - checked first
2. **Home directory** (`~/.patchpal/repos/<repo-name>/MEMORY.md`) - only used if #1 doesn't exist

This means:
- If you create `MEMORY.md` in your repo root, PatchPal will use that (and ignore home directory)
- If you remove `MEMORY.md` from repo root, PatchPal falls back to home directory
- You can't combine both - only one location is active

## Checking Which Location is Active

The agent is informed which MEMORY.md file is being used through a system message. You can ask the agent "Which MEMORY.md file are you using?" to see the active location.

Alternatively, you can check manually:
```bash
# Check if repo root has MEMORY.md
ls -la MEMORY.md

# Check home directory location
ls -la ~/.patchpal/repos/$(basename $(pwd))/MEMORY.md
```

If the repository root has `MEMORY.md`, that's what's being used. Otherwise, the home directory version is active.

## Availability

Project memory is available in:
- **CLI mode**: Loaded automatically at startup
- **Python API**: Loaded automatically when agent is created
- **Autopilot mode**: Available throughout autonomous execution

## Example MEMORY.md

```markdown
# Project Notes

This file persists across PatchPal sessions.

## Project Context
This is a REST API for managing user accounts built with FastAPI.

## Important Decisions
- Using PostgreSQL for the database (MySQL had performance issues)
- JWT tokens expire after 24 hours
- API rate limit: 100 requests per minute per IP

## Key Facts
- Production: https://api.example.com
- Database: PostgreSQL 14 on RDS
- Redis cache on ElastiCache

## Known Issues
- TODO: Add pagination to /users endpoint
- TODO: Implement proper error logging
- Technical debt: Refactor authentication module

## Team Conventions
- Use Black for code formatting
- All API endpoints require authentication except /health
- Write tests for all new endpoints
```
