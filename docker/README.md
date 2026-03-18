# PatchPal Sandbox Docker Images

This directory contains Dockerfiles for building pre-configured sandbox images.

## Images

### `patchpal-sandbox` (Dockerfile-sandbox)

Pre-built image with patchpal installed, optimized for fast startup.

**Image**: `ghcr.io/amaiya/patchpal-sandbox:latest`

**Features**:
- Python 3.11-slim base
- Pre-installed patchpal and all dependencies
- Git, curl, and CA certificates included
- ~150MB total size
- No pip install needed on container start (instant startup)

**Usage**:

```bash
# Pull the image (one-time, ~150MB)
docker pull ghcr.io/amaiya/patchpal-sandbox:latest

# Use with patchpal-sandbox (default)
patchpal-sandbox -- --model openai/gpt-5.2-codex

# Use with custom image for latest patchpal from PyPI
patchpal-sandbox --image python:3.11-slim -- --model openai/gpt-5.2-codex
```

**Building locally**:

```bash
cd /path/to/patchpal
docker build -f docker/Dockerfile-sandbox -t patchpal-sandbox:local .
```

## GitHub Actions

The sandbox image is automatically built and pushed to GHCR on:
- Push to main/master branch (when Dockerfile or workflow changes)
- Release publication (tagged with version)
- Manual workflow dispatch

**Tags**:
- `latest` - Latest build from main branch
- `vX.Y.Z` - Specific version releases
- `X.Y` - Major.minor version

## Performance Comparison

| Scenario | Image | Startup Time | Notes |
|----------|-------|--------------|-------|
| **Default (pre-built)** | `ghcr.io/amaiya/patchpal-sandbox:latest` | ~1-2s | Image cached, no pip install |
| **First run** | `ghcr.io/amaiya/patchpal-sandbox:latest` | ~20-30s | One-time download (~150MB) |
| **PyPI latest** | `python:3.11-slim` | ~10-30s | Every run, pip installs patchpal |
| **PyPI first run** | `python:3.11-slim` | ~40-60s | Downloads base + pip install |

**Recommendation**: Use default pre-built image for production and frequent use. Use `python:3.11-slim` for development when testing latest patchpal changes from PyPI.

## Maintenance

**Updating the image**:
1. Update `Dockerfile-sandbox` if needed
2. Commit and push to main branch
3. GitHub Actions automatically builds and pushes new image
4. Users pull with `docker pull ghcr.io/amaiya/patchpal-sandbox:latest`

**Version releases**:
When creating a new patchpal release (e.g., v0.22.0):
1. Tag the release in GitHub
2. GitHub Actions builds image tagged as `0.22.0`, `0.22`, and `latest`
3. Users can pin to specific version: `--image ghcr.io/amaiya/patchpal-sandbox:0.22`

## Integration with onprem

The `onprem` package's `AgentExecutor` uses patchpal-sandbox internally:

```python
from onprem.pipelines.agent import AgentExecutor

# Uses pre-built image by default when sandbox=True
executor = AgentExecutor(
    model='anthropic/claude-sonnet-4-5',
    sandbox=True  # Uses ghcr.io/amaiya/patchpal-sandbox:latest
)

# Or specify custom image
executor = AgentExecutor(
    model='anthropic/claude-sonnet-4-5',
    sandbox=True,
    image='python:3.11-slim'  # Get latest from PyPI
)
```

## Troubleshooting

**Image pull fails**:
```bash
# Fallback to PyPI
patchpal-sandbox --image python:3.11-slim -- --model openai/gpt-5.2-codex
```

**Need specific patchpal version**:
```bash
# Use version-tagged image
patchpal-sandbox --image ghcr.io/amaiya/patchpal-sandbox:0.21 -- --model openai/gpt-5.2-codex

# Or install specific version from PyPI
docker run -it --rm python:3.11-slim bash -c "pip install patchpal==0.21.0 && patchpal --version"
```

**Corporate firewall/proxy**:
- Pre-built image is publicly available on GitHub Container Registry
- No authentication needed for public images
- Bypasses PyPI entirely (useful for restrictive networks)
