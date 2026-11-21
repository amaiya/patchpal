---
name: commit
description: Create a well-formatted git commit following best practices
---

# Git Commit Workflow

Follow these steps to create a high-quality commit:

## 1. Review Changes
- Use `run_shell` to execute: `git status` to see what files have changed
- Use `run_shell` to execute: `git diff` to review the actual changes
- Ensure you understand what's being committed

## 2. Write Commit Message
Create a commit message that:
- Starts with a concise summary (50 chars or less)
- Uses imperative mood ("Add feature" not "Added feature")
- Includes details in the body if needed
- References any relevant issue numbers

## 3. Stage and Commit
- Stage only the relevant files (avoid staging unrelated changes)
- Use `run_shell` to execute: `git add <files>`
- Use `run_shell` to execute: `git commit -m "Your message"`

## 4. Verify
- Use `run_shell` to execute: `git log -1 --stat` to confirm the commit was created correctly
- Use `run_shell` to execute: `git diff --staged` to ensure nothing unexpected was committed

## Format Example
```
Add user authentication feature

- Implement JWT token generation
- Add login/logout endpoints
- Update user model with password hashing

Fixes #123
```
