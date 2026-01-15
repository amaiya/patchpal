# Publishing PatchPal to PyPI

This guide explains how to publish PatchPal to PyPI.

## Prerequisites

1. Create an account on [PyPI](https://pypi.org/) and [TestPyPI](https://test.pypi.org/)
2. Install required tools:
   ```bash
   pip install build twine
   ```

## Build the Package

1. Clean previous builds (if any):
   ```bash
   rm -rf dist/ build/ *.egg-info
   ```

2. Build the package:
   ```bash
   python -m build
   ```

   This creates both a wheel (`.whl`) and source distribution (`.tar.gz`) in the `dist/` directory.

## Test on TestPyPI (Recommended)

Before publishing to the real PyPI, test on TestPyPI:

1. Upload to TestPyPI:
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

2. Test installation:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ --no-deps patchpal
   ```

## Publish to PyPI

Once you've tested everything:

1. Upload to PyPI:
   ```bash
   python -m twine upload dist/*
   ```

2. You'll be prompted for your PyPI credentials (or use an API token).

3. Verify the package:
   ```bash
   pip install patchpal
   ```

## Using API Tokens (Recommended)

Instead of username/password, use API tokens:

1. Generate a token on [PyPI](https://pypi.org/manage/account/token/)
2. Create/edit `~/.pypirc`:
   ```ini
   [pypi]
   username = __token__
   password = pypi-YOUR_TOKEN_HERE

   [testpypi]
   username = __token__
   password = pypi-YOUR_TEST_TOKEN_HERE
   ```

## Version Updates

To release a new version:

1. Update version in `pyproject.toml`
2. Update `__version__` in `patchpal/__init__.py`
3. Commit changes
4. Create a git tag:
   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```
5. Rebuild and upload

## Automated Publishing with GitHub Actions

Consider setting up GitHub Actions for automated publishing. Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

Add your PyPI API token as a secret in your GitHub repository settings.
