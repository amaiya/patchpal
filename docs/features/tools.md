# Built-In Tools

PatchPal provides 33 built-in tools for file operations, code analysis, web access, browser automation, task planning, and user interaction.

> **For Local Models:** Set `PATCHPAL_MINIMAL_TOOLS=true` and `PATCHPAL_ENABLE_WEB=false` to use only 5 essential tools (`read_file`, `read_lines`, `write_file`, `edit_file`, `run_shell`), reducing tool confusion with smaller models.

> **Optional Tools:** Some tools (`grep`, `find`) are disabled by default because shell commands are preferred for flexibility. They can be enabled via `enabled_tools` parameter or `PATCHPAL_ENABLED_TOOLS` environment variable for scenarios where you need search/navigation without shell access.

## File Reading (2 tools)

### read_file
Read contents of files anywhere on the system (repository files, logs, configs).

- **Example**: `read_file("src/app.py")`
- Supports text files, images (PNG, JPG, GIF, etc.), and documents (PDF, DOCX, PPTX)
- **Image Support**: When using vision-capable models (GPT-4o, Claude 3.5 Sonnet), images are automatically formatted for the model
  - Example: Just mention image files in your prompt: "Look at screenshot.png and tell me what's wrong"
  - Supported formats: PNG, JPG, JPEG, GIF, BMP, WEBP (SVG returned as text)
  - The agent will automatically call `read_file` on image files when needed
  - **Size limits**:
    - Maximum file size: 10MB (configurable with `PATCHPAL_MAX_IMAGE_SIZE`)
    - Provider limits: OpenAI (20MB), Anthropic/Bedrock (5MB)
    - Images bypass tool output truncation limits (100K chars)
  - **Multi-provider support**:
    - **Anthropic/Claude**: Images in tool results (multimodal content)
    - **OpenAI/GPT**: Images injected as user messages (API limitation workaround)
    - Automatic detection and formatting based on model provider
  - **Non-vision models**: Set `PATCHPAL_BLOCK_IMAGES=true` to replace images with text placeholders
    - Prevents API errors from non-vision models (gpt-3.5-turbo, claude-instant, local models)
    - Also useful for privacy compliance (prevent image data from being sent to LLM)
  - **Recommendation**: Use compressed images for faster processing (1-2MB optimal)
- Text file limit: 500KB by default (configurable with `PATCHPAL_MAX_FILE_SIZE`)
- For larger files, use `read_lines` for targeted access

### read_lines
Read specific line ranges from a file without loading the entire file.

- **Example**: `read_lines("app.py", 100, 150)` - read lines 100-150
- More efficient than `read_file` when you only need a few lines
- Useful for viewing code sections, error context, or specific regions

## File Writing (2 tools)

### write_file
Modify files by replacing entire contents.

- **Example**: `write_file("config.py", new_content)`
- Use for large-scale changes or multiple edits
- Returns unified diff showing changes
- Best for rewriting entire files or complex modifications

### edit_file
Edit a file by replacing an exact string (efficient for small changes).

- **Example**: `edit_file("config.py", "port = 3000", "port = 8080")`
- More efficient than `write_file` for targeted changes
- Old string must appear exactly once in the file
- Best for single-line or small multi-line edits

## Shell (1 tool)

### run_shell
Execute shell commands in the repository.

- **Example**: `run_shell("pytest tests/test_auth.py")`
- **Example**: `run_shell("npm install lodash")`
- Commands execute from repository root automatically (no need for `cd`)
- **80+ harmless commands auto-granted** (no permission prompts):
  - File operations: `wc`, `stat`, `find`, `ls`, `cat`, `head`, `tail`
  - Search: `grep`, `awk`
  - Git (read-only): `git status`, `git diff`, `git log`
  - Test runners: `pytest`, `jest`, `mocha`, `go test`, `cargo test`, `mvn test`, `dotnet test`, etc.
  - System info: `whoami`, `hostname`, `date`, `uname`
  - Network diagnostics: `ping`, `tracert`, `nslookup`
- Dangerous commands require permission (e.g., `rm`, `pip install`, script execution)
- Privilege escalation blocked by default (set `PATCHPAL_ALLOW_SUDO=true` to enable)

## Web Tools (2 tools)

### web_search
Search the web using DuckDuckGo (no API key required).

- **Example**: `web_search("Python asyncio best practices")`
- Look up error messages and solutions
- Find current documentation and best practices
- Research library versions and compatibility
- Returns top search results with titles, snippets, and URLs

### web_fetch
Fetch and read content from URLs.

- **Example**: `web_fetch("https://docs.python.org/3/library/asyncio.html")`
- Read documentation pages and API references
- Extract text from HTML, PDF, DOCX (Word), and PPTX (PowerPoint)
- Supports plain text, JSON, XML, and other text formats
- Warns about unsupported binary formats (images, videos, archives)

## Browser Automation (13 tools - optional)

> **Optional Feature:** Browser automation tools require Playwright. Install with:
> ```bash
> pip install patchpal[browser]
> python -m playwright install chromium
> ```
> This installs both Playwright and nest-asyncio (required to prevent event loop conflicts).
>
> **Security Note:** Browser tools respect the `PATCHPAL_ENABLE_WEB` environment variable. If web tools are disabled (`PATCHPAL_ENABLE_WEB=false`), browser tools are also disabled.
>
> To disable **only** the browser tools while keeping `web_search`/`web_fetch`, set `PATCHPAL_ENABLE_BROWSER=false` (default: `true`).

Interactive browser automation for JavaScript-heavy sites, forms, dynamic content, and complex web interactions that `web_fetch` cannot handle.

### When to Use Browser Tools vs web_fetch

| Use Case | Tool | Why |
|----------|------|-----|
| Static HTML pages | `web_fetch` | Faster, lighter |
| REST APIs / JSON | `web_fetch` | Direct HTTP request |
| Documentation sites | `web_fetch` | Static content |
| Single-page applications (React, Vue) | `browser_*` | Needs JS execution |
| Forms with validation | `browser_*` | Interactive input |
| Login flows | `browser_*` | Session management |
| Dynamic content loading | `browser_*` | Wait for AJAX |

### TLS / Certificate Handling (Corporate Proxies & Self-Signed Certs)

#### Installing Playwright Behind Corporate Proxies

When **installing** Playwright browser binaries (`python -m playwright install chromium`), Node.js downloads browser files over HTTPS. If behind a corporate proxy with self-signed certificates, you may see `SELF_SIGNED_CERT_IN_CHAIN` errors during installation.

**Solution:** Set `NODE_EXTRA_CA_CERTS` to your corporate certificate bundle **before** installation:

```bash
# Linux/WSL:
export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
python -m playwright install chromium

# Windows (PowerShell):
$env:NODE_EXTRA_CA_CERTS="C:\path\to\corporate-cert.crt"
python -m playwright install chromium

# Windows (CMD):
set NODE_EXTRA_CA_CERTS=C:\path\to\corporate-cert.crt
python -m playwright install chromium
```

For Windows, you may need to export your corporate certificate from the Windows Certificate Store:
- Press `Win+R`, type `certmgr.msc`
- Navigate to: **Trusted Root Certification Authorities** → **Certificates**
- Find your corporate certificate, right-click → **All Tasks** → **Export**
- Choose **Base-64 encoded X.509 (.CER)** and save
- Set `NODE_EXTRA_CA_CERTS` to the exported file path

See also `devsetup/win11.md` and `devsetup/wsl.md` for environment setup details.

#### Using the Browser at Runtime

Unlike `web_fetch`/`web_search` (which use `requests` and honor `PATCHPAL_VERIFY_SSL`, `SSL_CERT_FILE`, and `REQUESTS_CA_BUNDLE`), the Chromium browser launched by Playwright **does not** read a PEM CA-bundle file for page navigation. Setting `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, or `NODE_EXTRA_CA_CERTS` has **no effect** on the browser's page TLS (`NODE_EXTRA_CA_CERTS` only affects Node's HTTPS when *downloading* the browser binaries, not runtime).

By default the browser validates certificates against the OS/NSS trust store. If you are behind a corporate TLS-inspecting proxy or use self-signed certs, you have two options:

**Option 1 — Trust your CA (secure, recommended).** Import the CA into the NSS database Chromium reads on Linux (this is [documented by Chromium](https://chromium.googlesource.com/chromium/src/+/main/docs/linux/cert_management.md)):

```bash
# 1. Install the NSS command-line tools
sudo apt install libnss3-tools          # Debian/Ubuntu
# sudo dnf install nss-tools            # Fedora
# sudo zypper install mozilla-nss-tools # openSUSE

# 2. Locate the NSS DB Chromium uses:
#      - Chromium M146+ default: $HOME/.local/share/pki/nssdb
#      - Older / if it already exists: $HOME/.pki/nssdb
#    Chromium prefers an existing $HOME/.pki/nssdb if present.
NSSDB="$HOME/.local/share/pki/nssdb"
mkdir -p "$NSSDB"
certutil -d "sql:$NSSDB" -N --empty-password 2>/dev/null || true   # init if empty

# 3a. Import a single root CA (trust for issuing SSL server certs)
certutil -d "sql:$NSSDB" -A -t "C,," -n corp-ca -i /path/to/corporate-ca.pem
#     Intermediate CA:  use -t ",,"
#     Self-signed *server* cert (not a CA): use -t "P,,"

# 3b. If REQUESTS_CA_BUNDLE points at a bundle with MULTIPLE certs,
#     split it and import each one (certutil imports one cert per call):
csplit -z -f corpca- "$REQUESTS_CA_BUNDLE" '/-----BEGIN CERTIFICATE-----/' '{*}'
i=0; for f in corpca-*; do certutil -d "sql:$NSSDB" -A -t "C,," -n "corp-ca-$i" -i "$f"; i=$((i+1)); done

# 4. Verify
certutil -d "sql:$NSSDB" -L
```

After importing, the browser will trust sites signed by that CA without any further configuration.

**Option 2 — Bypass verification (insecure).** Accept any certificate in the browser:

```bash
export PATCHPAL_BROWSER_IGNORE_HTTPS_ERRORS=true   # browser-only bypass
# (PATCHPAL_VERIFY_SSL=false also enables this, and additionally disables
#  verification for web_search/web_fetch)
```

This is the quickest fix but disables certificate validation entirely (vulnerable to MITM), so prefer Option 1 in production.

### browser_navigate
Navigate to a URL in a visible Chromium browser window.

- **Example**: `browser_navigate("https://example.com")`
- Browser stays open for subsequent operations (stateful session)
- Applies same security checks as `web_fetch` (domain filtering, rate limiting)
- Returns page title and URL confirmation

### browser_click
Click an element using flexible selectors.

- **Examples**:
  - `browser_click("#submit-button")` - CSS selector
  - `browser_click("text=Login")` - Text content
  - `browser_click("role=button:Submit")` - ARIA role
- Browser must be open first via `browser_navigate`
- Returns confirmation with current URL

### browser_fill
Fill form fields with text.

- **Examples**:
  - `browser_fill("#email", "user@example.com")` - CSS selector
  - `browser_fill("placeholder=Email", "user@example.com")` - Placeholder text
  - `browser_fill("label=Password", "secret123")` - Label text
- Clears existing content by default
- Browser must be open first

### browser_screenshot
Take a full-page screenshot.

- **Example**: `browser_screenshot("/tmp/page.png")`
- Saves as PNG file
- Useful for debugging or capturing visual state
- Returns path to saved screenshot

### browser_get_text
Extract all visible text from the page after JavaScript execution.

- **Example**: `browser_get_text()`
- Unlike `web_fetch`, this gets rendered content (post-JS)
- Useful for single-page applications and dynamically loaded content
- Returns title, URL, and page text (truncated at 20KB by default)
- Integrates with web_fetch's URL tracking for security

### browser_wait
Wait for a duration or element to appear.

- **Examples**:
  - `browser_wait(2000)` - Wait 2 seconds
  - `browser_wait(5000, "#results")` - Wait up to 5s for element
- Useful for waiting for dynamic content to load
- Maximum wait time: 30 seconds

### browser_close
Close the browser and cleanup resources.

- **Example**: `browser_close()`
- Safe to call even if browser is already closed
- Releases browser process and memory

### browser_get_html
Get the HTML source code from the current page or frame.

- **Example**: `browser_get_html()`
- Shows actual HTML structure with `<input>`, `<select>`, and form element IDs/names
- Particularly useful for identifying field selectors for `browser_fill()` on complex forms
- Unlike `browser_get_text()` which shows only visible text, this shows raw HTML
- Essential for sites with framesets or complex form structures
- Returns HTML content (truncated at 50KB by default)

### browser_list_frames
List all frames/iframes in the current page.

- **Example**: `browser_list_frames()`
- Shows frame indices, names, and URLs
- Essential for older government and enterprise sites using framesets
- Use with `browser_switch_frame()` to interact with content inside frames
- Returns "No frames found" if page uses standard layout

### browser_switch_frame
Switch to a frame/iframe for interaction.

- **Examples**:
  - `browser_switch_frame(index=1)` - Switch to first frame
  - `browser_switch_frame(name='content')` - Switch by frame name
  - `browser_switch_frame()` - Return to main page
- Many older sites (especially government/enterprise) use framesets
- Normal browser tools only work in the current frame context
- After switching, all subsequent operations target that frame
- Essential for sites like DoD portals, legacy enterprise applications

### browser_scroll
Scroll the page to load lazy-loaded content or navigate long pages.

- **Examples**:
  - `browser_scroll(direction="down")` - Scroll down one viewport
  - `browser_scroll(direction="down", amount=500)` - Scroll 500px
  - `browser_scroll(direction="bottom")` - Scroll to page bottom
  - `browser_scroll(selector="#footer")` - Scroll to specific element
- Essential for infinite scroll sites (Twitter, Reddit, Unsplash, social media feeds)
- Waits 1 second after scrolling for lazy content to load
- Returns scroll position and page height information
- Directions: `down`, `up`, `bottom`, `top`

### browser_dismiss_modals
Manually dismiss modal overlays blocking interaction.

- **Example**: `browser_dismiss_modals()`
- Attempts to close login prompts, newsletter signups, cookie notices, app download prompts
- `browser_navigate()` and `browser_click()` already auto-dismiss modals
- Use this if modals still block actions after navigation/clicking
- Tries common close button selectors (ARIA labels, class names, X buttons)

### browser_execute_script
Execute JavaScript code in the current page and return the result.

- **Examples**:
  - `browser_execute_script("document.querySelectorAll('img').length")` - Count images
  - `browser_execute_script("document.title")` - Get page title
  - `browser_execute_script("document.querySelector('#email').value = 'test@example.com'")` - Fill form directly
  - `browser_execute_script("Array.from(document.querySelectorAll('a')).map(a => a.href)")` - Get all link URLs
- Allows direct DOM manipulation, querying elements, counting items
- Useful for complex interactions beyond standard browser tools
- Script must return a serializable value (string, number, array, object)
- Essential for:
  - Counting elements on infinite scroll sites
  - Complex form interactions
  - Triggering custom JavaScript events
  - Extracting structured data from the page
  - Session keep-alive for timeout-sensitive sites
- Returns formatted result (JSON for arrays/objects)

### Example Workflow: Form Submission

```python
# Navigate to form
browser_navigate("https://example.com/contact")

# Fill fields
browser_fill("label=Name", "John Doe")
browser_fill("label=Email", "john@example.com")
browser_fill("label=Message", "Test message")

# Submit and wait for confirmation
browser_click("text=Submit")
browser_wait(3000, ".success-message")

# Capture proof
browser_screenshot("/tmp/submission.png")

# Cleanup
browser_close()
```

### Example Prompt: Navigate, Search, and Extract

You can drive the browser tools with a single natural-language prompt. For example:

> Visit https://www.wikipedia.org, click on English, search for "Web scraping", and extract the first paragraph

PatchPal will translate this into a sequence of browser tool calls, roughly:

```python
# Open the Wikipedia portal
browser_navigate("https://www.wikipedia.org")

# Enter the English edition
browser_click("text=English")

# Search for the topic
browser_fill("#searchInput", "Web scraping")
browser_click("button[type=submit]")

# Wait for the article to render, then read the page
browser_wait(3000, "#mw-content-text")
browser_get_text()   # extract the article text (incl. the first paragraph)

# Cleanup
browser_close()
```

> **Tip:** If the target site uses a corporate/self-signed certificate, make sure
> the CA is trusted first (see [TLS / Certificate Handling](#tls--certificate-handling-corporate-proxies--self-signed-certs) above), otherwise navigation will fail with `net::ERR_CERT_AUTHORITY_INVALID`.

### Security Features

Browser tools inherit `web_fetch` security:
- Domain filtering (`PATCHPAL_WEB_ALLOWED_DOMAINS`, `PATCHPAL_WEB_BLOCKED_DOMAINS`)
- Rate limiting (`PATCHPAL_WEB_RATE_LIMIT`)
- Permission system (requires approval like other tools)
- URL validation (must start with `http://` or `https://`)

### Implementation Details

- **Browser**: Chromium via Playwright
- **Visibility**: Non-headless by default (visible browser)
- **Viewport**: 1280x900
- **Timeouts**: 30s navigation, 10s interactions
- **Session**: Single persistent browser instance across tools

## Code Analysis (2 tools)

### code_structure
Analyze code structure using tree-sitter AST parsing without reading full files.

- **Example**: `code_structure("app.py")` - see all classes, functions, methods with line numbers
- **95% token savings** vs `read_file` for large code files
- Supports **40+ languages**: Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, Ruby, PHP, and more
- Shows function signatures and line numbers for easy navigation
- **Best practice**: Use with `read_lines` - analyze structure first, then read specific sections

### get_repo_map
Get an overview of the entire codebase in one call.

- **Example**: `get_repo_map(max_files=100)` - see structure of up to 100 files at once
- Shows function/class signatures from ALL files in a consolidated view
- **Filtering**: `get_repo_map(include_patterns=["*.py"], exclude_patterns=["*test*"])`
- **38-70% token savings** vs calling `code_structure` on each file individually
- Ideal for understanding codebase structure and finding relevant files

## Task Planning (6 tools)

### todo_add
Add a new task to break down complex work into manageable subtasks.

- **Example**: `todo_add("Implement authentication", details="Use JWT tokens")`
- Each task gets a unique ID for tracking
- Use for multi-step workflows

### todo_list
Show all tasks with their status and progress.

- **Example**: `todo_list()` - show pending tasks only
- **Example**: `todo_list(show_completed=True)` - show all tasks including completed

### todo_complete
Mark a task as done.

- **Example**: `todo_complete(1)` - mark task #1 as completed

### todo_update
Update task description or details.

- **Example**: `todo_update(1, description="Implement OAuth2 authentication")`

### todo_remove
Remove a task from the list.

- **Example**: `todo_remove(1)` - remove task #1

### todo_clear
Clear completed tasks or start fresh.

- **Example**: `todo_clear()` - clear completed tasks only
- **Example**: `todo_clear(completed_only=False)` - clear all tasks

## Skills (2 tools)

### list_skills
List all available skills (e.g., /commit, /test, /debug).

- Skills are higher-level commands that combine multiple tools
- Users invoke skills with `/skillname` syntax at the CLI

### use_skill
Invoke a skill programmatically when relevant to the request.

- **Example**: `use_skill("commit", args="Fix authentication bug")`
- Note: Users invoke skills via `/skillname` at CLI, not by calling this tool

## User Interaction (1 tool)

### ask_user
Ask the user a question during task execution.

- **Example**: `ask_user("Which database should I use?", options=["PostgreSQL", "MySQL", "SQLite"])`
- Useful for clarifying requirements, getting decisions, or gathering additional information
- Supports multiple choice options or free-form answers

## Optional Tools (2 tools - disabled by default)

These tools are disabled by default because shell commands provide more flexibility. Enable them via `enabled_tools` parameter when you need search/navigation without shell access.

### grep
Search for a pattern in files using grep or ripgrep.

- **Example**: `grep("def main", file_glob="*.py")`
- **Disabled by default** - use `run_shell("grep -r 'pattern' .")` for more flexibility
- **Enable when**: You need search without shell access (e.g., read-only security agents)
- Supports case-insensitive search, file globs, and path filtering
- Uses ripgrep if available (faster), falls back to grep
- **Requirements**: Requires `rg` (ripgrep) or `grep` command to be installed
  - macOS/Linux: `grep` usually pre-installed; install `ripgrep` for better performance
  - Windows: Install ripgrep via `choco install ripgrep` or `scoop install ripgrep`
- Enable: `agent = create_agent(enabled_tools=["read_file", "grep"])`

### find
Search for files by glob pattern.

- **Example**: `find()` - list all files in repository (sorted by modification time)
- **Example**: `find(path="src")` - list all files in src directory
- **Example**: `find("*.py")` - find all Python files
- **Example**: `find("**/*.test.js", path="src")` - find all test files in src directory
- **Disabled by default** - use `run_shell("find . -name '*.py'")` for more flexibility
- **Enable when**: You need fast file discovery without shell access or expensive code parsing
- Returns file paths sorted by modification time (most recent first)
- Respects .gitignore patterns automatically
- **Faster than** `get_repo_map` when you just need file paths (no structure analysis)
- Enable: `agent = create_agent(enabled_tools=["read_file", "find"])`

## Tool Count by Category

| Category | Tools | Count |
|----------|-------|-------|
| File Reading | read_file, read_lines | 2 |
| File Writing | write_file, edit_file | 2 |
| Shell | run_shell | 1 |
| Optional Tools* | grep, find | 2 |
| Code Analysis | code_structure, get_repo_map | 2 |
| Web | web_search, web_fetch | 2 |
| Browser Automation** | browser_navigate, browser_click, browser_fill, browser_screenshot, browser_get_text, browser_get_html, browser_list_frames, browser_switch_frame, browser_scroll, browser_execute_script, browser_wait, browser_dismiss_modals, browser_close | 13 |
| Task Planning | todo_add, todo_list, todo_complete, todo_update, todo_remove, todo_clear | 6 |
| Skills | list_skills, use_skill | 2 |
| User Interaction | ask_user | 1 |
| **Total** | | **33** |

*Optional tools are disabled by default (shell commands preferred)
**Browser tools require `pip install patchpal[browser]` and are disabled if Playwright not installed

## Configuration

### Environment Variables

- `PATCHPAL_MAX_FILE_SIZE` - Maximum file size for text files in read_file (default: 500KB)
- `PATCHPAL_MAX_IMAGE_SIZE` - Maximum image file size for read_file (default: 10MB)
- `PATCHPAL_BLOCK_IMAGES` - Block images from being sent to LLM (default: false)
- `PATCHPAL_ENABLE_WEB` - Enable/disable web tools (web_search, web_fetch, and browser_* tools) (default: true)
- `PATCHPAL_ALLOW_SUDO` - Allow sudo/su commands (default: false)
- `PATCHPAL_MINIMAL_TOOLS` - Use minimal tools mode: 4-6 core tools only (default: false)

### Minimal Tools Mode

When `PATCHPAL_MINIMAL_TOOLS=true`, only these tools are available:
- `read_file`, `read_lines`, `write_file`, `edit_file`, `run_shell`
- `web_search`, `web_fetch` (if `PATCHPAL_ENABLE_WEB=true`)

This reduces tool count to 4-6 for local models with tool confusion issues. Harmless shell commands still work without permission prompts.

## Permission System

### Read Operations (Auto-Granted)
- Reading repository files (including images)
- Listing files and directories
- Searching with grep
- Analyzing code structure
- Git read-only operations (status, diff, log)
- System information commands

### Write Operations (Require Permission)
- Editing/patching files outside repository
- Dangerous shell commands
- Web access (to prevent info leakage)
- Installation commands (pip, npm, etc.)

### Bypass Permission Prompts
Set `PATCHPAL_REQUIRE_PERMISSION=false` to auto-grant all operations (use carefully).
