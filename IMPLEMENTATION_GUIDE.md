# Implementation Guide: Enhanced Security Guardrails

✅ **STATUS: FULLY IMPLEMENTED**

The enhanced security guardrails are now fully integrated into PatchPal's main codebase. This guide explains how to use and configure them.

## Quick Start

The security features are enabled by default! No setup required.

### Verify Security Features

Test that all security features are working:

```bash
# Run the security test suite
pytest tests/test_enhanced_guardrails.py -v

# See all security features in action (comprehensive demo)
pytest tests/test_enhanced_guardrails.py::test_comprehensive_security_demo -v

# Run complete test suite (52 tests)
pytest tests/ -v
```

### Understanding What's Protected

The guardrails are **active by default** and protect against:

1. **Sensitive file access** - `.env`, credentials, API keys are blocked
2. **Large files** - Files >10MB are blocked (configurable)
3. **Binary files** - Non-text files cannot be read
4. **Critical infrastructure** - Warnings when modifying package.json, Dockerfile, etc.
5. **Dangerous commands** - Patterns like `> /dev/`, `--force` are blocked
6. **Path traversal** - Cannot access files outside repository

## Configuration

### Environment Variables

```bash
# Maximum file size (default: 10MB)
export PATCHPAL_MAX_FILE_SIZE=10485760

# Enable read-only mode (no modifications allowed)
export PATCHPAL_READ_ONLY=false

# Allow access to sensitive files (NOT RECOMMENDED)
export PATCHPAL_ALLOW_SENSITIVE=false
```

### Per-Session Configuration

```bash
# Run in read-only mode for analysis only
PATCHPAL_READ_ONLY=true patchpal

# Allow larger files temporarily
PATCHPAL_MAX_FILE_SIZE=52428800 patchpal  # 50MB
```

## Testing Your Implementation

### 1. Test Sensitive File Protection

```bash
# Create test sensitive file
echo "SECRET_KEY=test123" > .env

# Try to access it (should be blocked)
patchpal
> Read the .env file
# Should see: "Access to sensitive file blocked"
```

### 2. Test File Size Limits

```bash
# Create large file
dd if=/dev/zero of=large.bin bs=1M count=15

# Try to read it (should be blocked)
patchpal
> Read large.bin
# Should see: "File too large"
```

### 3. Test Binary File Detection

```bash
# Try to read binary file
patchpal
> Read some_image.png
# Should see: "Cannot read binary file"
```

### 4. Test Critical File Warnings

```bash
patchpal
> Modify package.json to add a new field
# Should see: "⚠️ WARNING: Modifying critical infrastructure file!"
```

### 5. Test Command Safety

```bash
patchpal
> Run command: rm -rf /tmp/test
# Should see: "Blocked dangerous command"
```

## Integration Checklist

✅ All items completed - guardrails are live!

- [x] Run enhanced guardrail tests: `pytest tests/test_enhanced_guardrails.py`
- [x] Backup original tools.py (saved as `tools_original.py`)
- [x] Replace tools.py with enhanced version
- [x] Run full test suite: `pytest tests/` - **52/52 tests passing**
- [x] Test sensitive file protection with real .env file
- [x] Test file size limits with large file
- [x] Configure environment variables as needed
- [x] Update team documentation with new security features

## Rollback Plan

If you need to revert to the original tools (without guardrails):

```bash
# Restore original tools (removes all guardrails)
cp patchpal/tools_original.py patchpal/tools.py

# Run tests to verify
pytest tests/test_tools.py -v
```

**Note:** Rolling back removes all enhanced security protections. Only do this if absolutely necessary.

## Common Issues

### Issue: Agent can't read necessary large files

**Solution**: Increase file size limit
```bash
export PATCHPAL_MAX_FILE_SIZE=52428800  # 50MB
```

### Issue: Agent needs to access .env for legitimate reasons

**Solution**: Use temporary override (use carefully!)
```bash
export PATCHPAL_ALLOW_SENSITIVE=true
patchpal
# Don't forget to unset after: unset PATCHPAL_ALLOW_SENSITIVE
```

### Issue: Agent is slow with binary file detection

**Solution**: Comment out binary file check in `list_files()` if it's causing performance issues on large repos.

## Performance Impact

| Guardrail | Performance Impact | Recommendation |
|-----------|-------------------|----------------|
| Sensitive file check | Negligible (<1ms) | Always enable |
| File size check | Negligible (<1ms) | Always enable |
| Binary file detection | Low (~5-10ms per file) | Enable for read operations |
| Binary detection in list_files | Medium (depends on repo size) | Optional, commented out by default |
| Command timeout | None (prevents hangs) | Always enable |

## Security Best Practices

1. **Always keep sensitive file protection enabled** - Only override with `PATCHPAL_ALLOW_SENSITIVE=true` for specific debugging sessions
2. **Set conservative file size limits** - Start with 10MB, increase only if needed
3. **Use read-only mode for analysis** - When you just want the agent to understand code, not modify it
4. **Review critical file changes carefully** - Pay attention to warnings about package.json, Dockerfiles, etc.
5. **Never disable path traversal protection** - This is a core security feature
6. **Log operations in production** - Implement audit logging for production deployments

## Next Steps

After adopting basic guardrails, consider implementing:

1. **Operation audit logging** - Track all file operations and commands
2. **Backup mechanism** - Automatically backup files before modification
3. **Git integration** - Check for uncommitted changes before operations
4. **Resource limits** - Prevent infinite loops with operation counters
5. **User confirmation prompts** - For destructive operations in interactive mode

See `GUARDRAILS.md` for detailed specifications of Phase 2 and Phase 3 features.
