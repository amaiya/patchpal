# Example Tasks

## Coding Tasks

```
Resolve this error message: "UnicodeDecodeError: 'charmap' codec can't decode"

Build a streamlit app to <whatever you want>

Create a bar chart for top 5 downloaded Python packages as of yesterday

Find and implement best practices for async/await in Python

Add GitHub CI/CD for this project

Add type hints and basic logging to mymodule.py

Create unit tests for the utils module

Refactor the authentication code for better security

Add error handling to all API calls

Look up the latest FastAPI documentation and add dependency injection
```

## Image Analysis Tasks

When using vision-capable models (GPT-4o, Claude 3.5 Sonnet, etc.), PatchPal can analyze images:

```
Look at screenshot.png and tell me what's wrong with the UI

Compare before.jpg and after.jpg - what changed?

Analyze this architecture diagram: system-design.png

What does this error screenshot show? error.png

Review the UI mockup in design.png and suggest improvements

Extract the text from this screenshot: terminal-output.png

Is the layout in homepage.jpg mobile-responsive?

Analyze this chart visualization.png and explain the trends
```

**How it works**: Simply mention image files in your prompt. The agent will automatically use the `read_file` tool to load and analyze them.

**Supported formats**: PNG, JPG, JPEG, GIF, BMP, WEBP (SVG is returned as text)
