# Background Automation Examples

This directory contains examples of using PatchPal's background automation features, inspired by the ClaudeClaw use cases.

## Contents

- `jobs/` - Example job definitions (YAML files)
- `scripts/` - Example Python scripts for data collection
- `README.md` - This file

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install patchpal[claw]  # Includes croniter + telegram
   ```

2. **Copy example jobs:**
   ```bash
   cp examples/automation/jobs/* ~/.patchpal/jobs/
   ```

3. **Copy example scripts:**
   ```bash
   cp examples/automation/scripts/* ~/.patchpal/scripts/
   ```

4. **Edit jobs to customize:**
   ```bash
   nano ~/.patchpal/jobs/reddit-listening.yaml
   ```

5. **Start the daemon:**
   ```bash
   patchpal-daemon
   ```

## Example Use Cases

### 1. Reddit Listening

**What it does:**
- Searches Reddit every 15 minutes
- Filters for posts about specific topics
- Deduplicates using cache
- Sends top 3 posts to Telegram

**Files:**
- `jobs/reddit-listening.yaml` - Job definition
- `scripts/reddit_search.py` - Search script

**Setup:**
```bash
# Install Reddit API library
pip install praw

# Configure Reddit API (get from https://www.reddit.com/prefs/apps)
export REDDIT_CLIENT_ID="your-client-id"
export REDDIT_CLIENT_SECRET="your-secret"
export REDDIT_USER_AGENT="patchpal/1.0"
```

### 2. LinkedIn Enrichment

**What it does:**
- Searches LinkedIn for interesting people
- Uses intercepted API (no Selenium needed!)
- Identifies founders, builders, technical folks
- Suggests personalized connection messages

**Files:**
- `jobs/linkedin-enrichment.yaml` - Job definition
- `scripts/linkedin_search.py` - Search script with API interception guide

**Setup:**
See `scripts/linkedin_search.py` for detailed instructions on:
1. How to intercept LinkedIn's search API
2. How to extract cookies from your browser
3. How to store credentials securely

**Note:** This uses LinkedIn's internal API, not Selenium/Puppeteer. Much faster and more reliable!

### 3. Daily Tracker

**What it does:**
- Morning check-in (9 AM): Shows your priorities
- Evening review (9 PM): Checks what you completed
- Uses git commits to track progress
- Keeps you accountable

**Files:**
- `jobs/daily-morning.yaml` - Morning check-in
- `jobs/daily-evening.yaml` - Evening review

**Setup:**
Edit your `MEMORY.md` to include daily priorities:

```bash
nano ~/.patchpal/repos/your-project/MEMORY.md
```

Add a section like:
```markdown
## Daily Priorities
- [ ] Review pull requests
- [ ] Write documentation
- [ ] Fix critical bugs
```

## Job File Format

Jobs are defined in `~/.patchpal/jobs/*.yaml`:

```yaml
# Schedule (cron format)
schedule: "*/15 * * * *"  # Every 15 minutes

# Model to use (optional, uses default if not specified)
model: "anthropic/claude-sonnet-4"

# Enable/disable the job
enabled: true

# Send Telegram notifications
notify: true

# The prompt to execute
prompt: |
  Run the search script and analyze results:

  run_shell python ~/.patchpal/scripts/my_script.py "query"

  Analyze the top 3 results and report interesting findings.
```

## Cron Expression Examples

| Expression | Meaning |
|------------|---------|
| `*/15 * * * *` | Every 15 minutes |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Daily at 9 AM |
| `0 9,21 * * *` | Daily at 9 AM and 9 PM |
| `0 9 * * 1-5` | Weekdays at 9 AM |

## Telegram Notifications

1. **Create a bot:**
   ```
   1. Open Telegram, talk to @BotFather
   2. Send: /newbot
   3. Follow prompts, copy bot token
   ```

2. **Get your chat ID:**
   ```
   1. Send a message to your bot
   2. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
   3. Copy the chat ID from response
   ```

3. **Set environment variables:**
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
   export TELEGRAM_CHAT_ID="123456789"
   ```

4. **Test it:**
   ```bash
   python -c "from patchpal.claw.telegram import send; send('Hello from PatchPal!')"
   ```

## Script Writing Tips

### 1. Use the Cache System

```python
from patchpal.claw.cache import get, set, is_duplicate, add_to_set

# Check if we've seen this post before
if not is_duplicate('reddit_seen', post_id):
    print(f"New post: {post_id}")
    add_to_set('reddit_seen', post_id)
```

### 2. Return Structured Data

```python
import json

results = [
    {'title': 'Post 1', 'score': 100},
    {'title': 'Post 2', 'score': 50}
]

# Claude can easily parse JSON
print(json.dumps(results, indent=2))
```

### 3. Use API Interception (Not Browser Automation)

Instead of Selenium/Puppeteer:

```python
# Intercept the API endpoint from browser DevTools
import requests

response = requests.get(
    'https://www.example.com/api/search',
    headers={
        'Cookie': 'session=abc123...',
        'User-Agent': 'Mozilla/5.0...'
    },
    params={'q': 'search query'}
)

data = response.json()
```

This is:
- ✅ 10x faster than browser automation
- ✅ More reliable (no DOM selectors)
- ✅ Lower resource usage
- ✅ What the OP of ClaudeClaw used successfully

## Monitoring

### Check daemon status:
```bash
patchpal-daemon --status
```

### List all jobs:
```bash
patchpal-daemon --list-jobs
```

### View job logs:
```bash
# Daemon logs to stdout
patchpal-daemon 2>&1 | tee ~/patchpal-daemon.log
```

## Troubleshooting

### Job not running?
```bash
# Check if job is enabled
patchpal-daemon --list-jobs

# Check schedule is valid
python -c "from croniter import croniter; croniter('*/15 * * * *')"

# Check for errors
patchpal-daemon --debug
```

### Script failing?
```bash
# Test script manually
python ~/.patchpal/scripts/my_script.py "test"

# Check permissions
ls -la ~/.patchpal/scripts/

# Check environment variables
env | grep REDDIT
```

### Telegram not working?
```bash
# Test credentials
python -c "from patchpal.claw.telegram import send; send('Test')"

# Check config
python -c "from patchpal.claw.telegram import is_configured; print(is_configured())"
```

## Comparison with ClaudeClaw/OpenClaw

PatchPal provides similar automation capabilities but with a Python-native approach:

| Feature | PatchPal | ClaudeClaw | OpenClaw |
|---------|----------|------------|----------|
| Cron scheduling | ✅ | ✅ | ✅ |
| Telegram | ✅ | ✅ | ✅ |
| Python scripts | ✅ (native) | ❌ (JS only) | ❌ (JS only) |
| Custom tools | ✅ | ✅ | ✅ |
| Cache helpers | ✅ (built-in) | ❌ | ❌ |
| Setup time | 5 min | 5 min | 15-20 hours |
| Codebase size | ~1k LOC | ~4k LOC | 600k LOC |
| Security | ✅✅✅ | ✅✅ | ❌ |

## Real-World Results

From the Reddit thread about ClaudeClaw:

> "LinkedIn enrichment: my favourite! finds people talking about claude code and founders building interesting things to connect with, genuinely game changing for finding the right people"
>
> "Before this my LinkedIn was full of garbage not relevant to what i do, and all my old connections were oldschool ancient people, so my posts were literally getting 3 likes mostly from my 1st circle, now my network jumped to 300+ new connections and recruiters are hunting me"

The key insight: **The framework is less important than custom logic + AI analysis.**

PatchPal gives you the same capabilities with better Python integration.

## Contributing

Have a useful automation script? Submit a PR to add it to these examples!
