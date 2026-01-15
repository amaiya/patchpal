# Security Guardrails - Implementation Status

✅ **STATUS: PHASE 1 FULLY IMPLEMENTED**

This document outlines the security guardrails in PatchPal, inspired by Claude Code's safety mechanisms.

## Implemented Guardrails (Phase 1) ✅

PatchPal now implements all critical security features:

1. **Path Restriction**: All file operations restricted to repository root
2. **Command Blocking**: Dangerous commands blocked (rm, mv, sudo, chmod, etc.)
3. **Hidden File Filtering**: Hidden files (.git/, .env) excluded from listings
4. **Sensitive File Protection**: Blocks access to .env, credentials, API keys
5. **File Size Limits**: Prevents OOM with 10MB default limit (configurable)
6. **Binary File Detection**: Blocks reading non-text files
7. **Critical File Warnings**: Warns when modifying package.json, Dockerfile, etc.
8. **Read-Only Mode**: Optional mode prevents all modifications
9. **Command Timeout**: 30-second timeout on all shell commands
10. **Pattern-Based Blocking**: Blocks dangerous patterns like `> /dev/`, `--force`

**Test Coverage**: 52 tests total, 20 dedicated security tests

## Recommended Future Guardrails (Phase 2 & 3)

### 1. Sensitive File Protection ✅ IMPLEMENTED

**Status**: ✅ Fully implemented and tested

**Implementation**:
- Blocks access to `.env*`, `credentials.json`, `.ssh/`, `.aws/`, etc.
- Configurable override with `PATCHPAL_ALLOW_SENSITIVE=true` (not recommended)
- 3 tests covering basic blocking, credentials, and override

**Configuration**: Set `PATCHPAL_ALLOW_SENSITIVE=true` only for debugging

### 2. File Size Limits ✅ IMPLEMENTED

**Status**: ✅ Fully implemented and tested

**Implementation**:
- Default 10MB limit for both read and write operations
- Configurable via `PATCHPAL_MAX_FILE_SIZE` environment variable
- Clear error messages showing size and limit

**Configuration**: `export PATCHPAL_MAX_FILE_SIZE=52428800` # 50MB

### 3. Binary File Detection ✅ IMPLEMENTED

**Status**: ✅ Fully implemented and tested

**Implementation**:
- Uses MIME type detection and null byte checking
- Blocks reading binary files with clear error message
- Shows detected MIME type in error

**Tests**: 2 tests covering binary blocking and text file allowance

### 4. Critical File Warnings ✅ IMPLEMENTED

**Status**: ✅ Fully implemented and tested

**Implementation**:
- Warns when modifying `package.json`, `pyproject.toml`, `Dockerfile`, etc.
- Shows prominent ⚠️ WARNING in output
- Does not block, just warns
- Diff still shown for review

**Tests**: 2 tests covering warning display and normal file behavior

### 5. Command Pattern Blocking ✅ IMPLEMENTED

**Status**: ✅ Partially implemented

**Implementation**:
- Blocks dangerous patterns: `> /dev/`, `rm -rf /`, `| dd`, `--force`
- 30-second timeout on all commands
- More granular than original token-based blocking

**Future Enhancement**: Could add allowlist for specific safe git/npm commands

### 6. Git State Awareness (MEDIUM PRIORITY)

**Issue**: Agent doesn't know about uncommitted changes, could cause conflicts.

**Recommendation**:
```python
def _check_git_status() -> dict:
    """Check git status before operations."""
    result = subprocess.run(['git', 'status', '--porcelain'],
                          capture_output=True, text=True)
    return {
        'has_uncommitted': bool(result.stdout),
        'changes': result.stdout
    }
```

**Action**: Warn when operating on files with uncommitted changes.

### 7. Operation Audit Log (LOW PRIORITY)

**Issue**: No record of what operations were performed.

**Recommendation**:
```python
import logging
from datetime import datetime

# Log all operations
audit_logger = logging.getLogger('patchpal.audit')

def apply_patch(path: str, new_content: str) -> str:
    audit_logger.info(f"PATCH: {path} at {datetime.now()}")
    # ... rest of function
```

**Action**: Log all file operations and commands for debugging/audit.

### 8. Backup Mechanism (LOW PRIORITY)

**Issue**: No easy way to undo destructive changes.

**Recommendation**:
```python
import shutil
from pathlib import Path

BACKUP_DIR = Path('.patchpal_backups')

def _backup_file(path: Path) -> Path:
    """Create backup before modification."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"{path.name}.{timestamp}"
    shutil.copy2(path, backup_path)
    return backup_path
```

**Action**: Automatically backup files before modification.

### 9. Resource Limits (MEDIUM PRIORITY)

**Issue**: Agent could create thousands of files or run commands in a loop.

**Recommendation**:
```python
class OperationLimiter:
    def __init__(self, max_ops=100):
        self.max_ops = max_ops
        self.operations = 0

    def check_limit(self):
        self.operations += 1
        if self.operations > self.max_ops:
            raise ValueError(f"Operation limit exceeded ({self.max_ops})")
```

**Action**: Limit number of operations per session to prevent abuse.

### 10. Read-Only Mode (LOW PRIORITY)

**Issue**: Sometimes you want agent to analyze only, not modify.

**Recommendation**:
```python
READ_ONLY_MODE = os.getenv('PATCHPAL_READ_ONLY', 'false').lower() == 'true'

def apply_patch(path: str, new_content: str) -> str:
    if READ_ONLY_MODE:
        raise ValueError("Cannot modify files in read-only mode")
```

**Action**: Add environment variable to disable all write operations.

## Priority Implementation Order

1. **Phase 1 (Critical)**:
   - Sensitive file protection
   - File size limits
   - Destructive operation warnings

2. **Phase 2 (Important)**:
   - Binary file detection
   - Command granularity improvements
   - Git state awareness

3. **Phase 3 (Nice to Have)**:
   - Operation audit log
   - Backup mechanism
   - Resource limits
   - Read-only mode

## Testing Requirements

Each guardrail should have:
- Unit tests demonstrating the protection works
- Tests for bypass attempts
- Performance tests (ensure checks don't slow down operations)

## Configuration

Guardrails should be configurable via:
- Environment variables (`PATCHPAL_MAX_FILE_SIZE`, `PATCHPAL_READ_ONLY`)
- Config file (`.patchpalrc`)
- Command-line flags (`--read-only`, `--allow-sensitive`)

## References

- Claude Code sandbox implementation
- GitHub Copilot workspace safety guidelines
- OWASP LLM Security recommendations
