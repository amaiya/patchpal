# PatchPal Claw - General AI Assistant

A general AI assistant that runs in the background, combining scheduled automation with conversational AI accessible via chat platforms.

## What Is PatchPal Claw?

PatchPal Claw transforms PatchPal into a **general AI assistant** inspired by ClaudeClaw and NanoClaw. It runs as a background daemon that:

1. **Chats with you** via Telegram/Discord
2. **Remembers conversations** across sessions
3. **Runs scheduled automation** (jobs)
4. **Proactively checks in** (HEARTBEAT)
5. **Maintains context** per-chat with MEMORY.md files

## Quick Start

```bash
# 1. Install dependencies
pip install patchpal[claw]

# 2. Setup Telegram (5 minutes)
# Talk to @BotFather on Telegram
# Create bot: /newbot
# Copy token
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."

# 3. Start daemon
patchpal-daemon

# 4. Chat with your bot
# Send on Telegram: "@patchpal hello"
```

That's it! Your AI assistant is now running and listening.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────────┐
│  Telegram   │─────>│   Message    │─────>│    Polling     │
│    Bot      │      │    Store     │      │     Loop       │
└─────────────┘      │  (SQLite)    │      └────────────────┘
                     └──────────────┘              │
┌─────────────┐              │                     ↓
│   Discord   │──────────────┤           ┌────────────────┐
│    Bot      │              │           │    Session     │
└─────────────┘              │           │    Manager     │
                             │           └────────────────┘
┌─────────────┐              │                     │
│  Scheduled  │──────────────┘                     ↓
│    Jobs     │                           ┌────────────────┐
└─────────────┘                           │  Agent + LLM   │
                                          └────────────────┘
                                                   │
                                                   ↓
                                          ┌────────────────┐
                                          │   Response     │
                                          └────────────────┘
```

**Design philosophy:**
- One process, simple architecture
- SQLite for persistence
- Per-chat isolation (conversations don't mix)
- Polling-based (no complex webhooks)

## Features

### 🤖 Chat Bot Integration

Talk to your AI assistant from anywhere:

- **Telegram** - Chat via Telegram bot
- **Discord** - Chat via Discord bot
- **Trigger word** - Only responds when you say `@patchpal`
- **Context aware** - Remembers your conversation history

### 💾 Persistent Memory

Each chat gets its own isolated context:

- **SQLite storage** - All messages stored persistently
- **Conversation history** - Last 20 messages always in context
- **Per-chat MEMORY.md** - Long-term memory files
- **Survives restarts** - Context preserved across daemon restarts

### 📅 Scheduled Automation

Run tasks on schedule (existing PatchPal feature):

- **Cron expressions** - Flexible scheduling
- **Python scripts** - Native script execution
- **Job notifications** - Results sent to chat (optional)
- **Cache system** - Built-in deduplication

### 💓 HEARTBEAT (Optional)

Proactive check-ins:

- **Periodic reviews** - Checks every 15 minutes (configurable)
- **Context aware** - Reviews recent conversations
- **Task reminders** - "You said you'd do X..."
- **Smart silence** - Only messages if something needs attention

## Setup Guide

### Telegram Setup (Recommended)

1. **Create bot:**
   ```
   Open Telegram → Talk to @BotFather
   Send: /newbot
   Follow prompts
   Copy bot token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   ```

2. **Configure:**
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
   ```

3. **Start daemon:**
   ```bash
   patchpal-daemon
   ```

4. **Test:**
   ```
   Open Telegram → Find your bot → Start chat
   Send: @patchpal hello
   Bot responds: "Hello! How can I help you?"
   ```

### Discord Setup

1. **Create application:**
   ```
   Visit: https://discord.com/developers/applications
   Click: "New Application"
   Go to: Bot → "Add Bot"
   Copy bot token
   ```

2. **Enable intents:**
   ```
   Bot settings → Enable "Message Content Intent"
   ```

3. **Invite to server:**
   ```
   OAuth2 → URL Generator
   Scopes: bot
   Permissions: Send Messages, Read Messages
   Copy URL → Open in browser → Select server
   ```

4. **Configure:**
   ```bash
   export DISCORD_BOT_TOKEN="MTA5..."
   ```

5. **Start daemon:**
   ```bash
   patchpal-daemon
   ```

6. **Test:**
   ```
   Discord → Any channel with bot
   Send: @patchpal hello
   Bot responds: "Hello! How can I help you?"
   ```

## Configuration

### Environment Variables

```bash
# Required (choose at least one)
TELEGRAM_BOT_TOKEN="..."     # Telegram bot token
DISCORD_BOT_TOKEN="..."      # Discord bot token

# Optional
HEARTBEAT_ENABLED="true"     # Enable proactive check-ins (default: false)
TRIGGER_PATTERN="@patchpal"  # Word to trigger responses (default: @patchpal)
```

### Command Line Options

```bash
# Default intervals
patchpal-daemon

# Custom intervals
patchpal-daemon \
  --job-interval 30 \          # Check jobs every 30s (default: 60)
  --message-interval 3 \       # Poll messages every 3s (default: 5)
  --heartbeat-interval 600     # Heartbeat every 10min (default: 900 = 15min)

# Enable debug logging
patchpal-daemon --debug

# Show status
patchpal-daemon --status
```

## Usage Examples

### Basic Conversation

```
You: @patchpal what's 2+2?
Bot: 2+2 equals 4.

You: @patchpal write a hello world in python
Bot: Here's a simple hello world:

print("Hello, World!")

You: thanks!
Bot: You're welcome! Let me know if you need anything else.
```

### Task Reminders

```
You: @patchpal remind me to review the PR in 2 hours
Bot: Got it, I'll remind you in 2 hours to review the PR.

[2 hours later, HEARTBEAT runs]
Bot: hey, it's been 2 hours - time to review that PR you mentioned
```

### Scheduled Jobs

Create `~/.patchpal/jobs/daily-summary.yaml`:

```yaml
schedule: "0 18 * * *"  # 6 PM daily
enabled: true
notify: true  # Send to all active chats
prompt: |
  Check today's logs and provide a brief summary.
  Any interesting events or issues?
```

Result: At 6 PM daily, all your chats receive the summary.

### Multi-Platform

You can chat from both Telegram AND Discord:

```
Telegram chat:
You: @patchpal what's the weather?
Bot: [checks weather]

Discord chat (same bot, different chat):
You: @patchpal summarize our telegram conversation
Bot: [accesses conversation history from Telegram chat]
```

Each chat is isolated but the bot can access all contexts if asked.

## File Structure

```
~/.patchpal/
├── messages.db              # SQLite database (all messages)
├── chats/                   # Per-chat memory files
│   ├── telegram_123_MEMORY.md
│   └── discord_456_MEMORY.md
└── jobs/                    # Scheduled jobs (existing)
    ├── reddit-listening.yaml
    └── daily-summary.yaml
```

## How It Works

### Message Flow

1. **User sends message** via Telegram/Discord
2. **Bot receives** and stores in SQLite
3. **Daemon polls** database every 5 seconds
4. **Checks for trigger** word (@patchpal)
5. **Loads context** from conversation history + MEMORY.md
6. **Runs agent** with full context
7. **Sends response** via bot
8. **Stores response** in database

### Session Management

Each chat gets its own session:

```python
# Telegram chat: telegram:123456
session1 = ChatSession(
    chat_id="telegram:123456",
    agent=Agent(),
    context=[last 20 messages],
    memory_file="~/.patchpal/chats/telegram_123456_MEMORY.md"
)

# Discord chat: discord:789012
session2 = ChatSession(
    chat_id="discord:789012",
    agent=Agent(),
    context=[different 20 messages],
    memory_file="~/.patchpal/chats/discord_789012_MEMORY.md"
)
```

Conversations never mix - fully isolated.

### HEARTBEAT Flow

Every 15 minutes (if enabled):

1. **Load all active chats** from database
2. **For each chat:**
   - Get last 10 messages
   - Build heartbeat prompt: "Check for pending tasks..."
   - Run agent
   - If response != "HEARTBEAT_OK": Send message
   - If response == "HEARTBEAT_OK": Stay silent
3. **Sleep** until next heartbeat

## Comparison with ClaudeClaw/NanoClaw

| Feature | PatchPal Claw | ClaudeClaw | NanoClaw |
|---------|---------------|------------|----------|
| **Platforms** | Telegram, Discord | Telegram, Discord | WhatsApp |
| **Architecture** | Python, SQLite | Node.js plugin | Node.js, Docker |
| **Jobs** | ✅ Cron-based | ✅ Cron-based | ✅ Cron-based |
| **Heartbeat** | ✅ Optional | ✅ Default | ❌ No |
| **Isolation** | Per-chat sessions | Single session | Containerized |
| **Memory** | MEMORY.md + SQLite | CLAUDE.md | CLAUDE.md |
| **Codebase** | ~1,300 LOC | ~5,000 LOC | ~2,000 LOC |
| **Setup** | 5 minutes | 5 minutes | 10 minutes |
| **Python native** | ✅ | ❌ (JS) | ❌ (JS) |

**Why PatchPal Claw:**
- Python native (no Node.js required)
- Simpler architecture (no containers/plugins)
- Works with existing PatchPal ecosystem
- Clean separation: automation + chat bot

## Advanced Usage

### Custom Trigger Per Chat

Edit database to set different triggers:

```sql
UPDATE chats
SET trigger_pattern = '@mybot'
WHERE chat_id = 'telegram:123456';
```

Now that chat responds to `@mybot` instead of `@patchpal`.

### Job Notifications to Specific Chat

Create a job that sends to a specific chat:

```yaml
schedule: "0 * * * *"
enabled: true
notify: false  # Don't broadcast
prompt: |
  Check server status.

  If issues found, send message to telegram:123456:
  run_shell echo "Server issue!" > /tmp/notify
```

### Accessing Job Results in Conversation

```
You: @patchpal what did the reddit job find today?
Bot: [reads cache from ~/.patchpal/cache/reddit_seen.json]
     Today's reddit search found 3 posts about AI agents...
```

The bot can access all job artifacts, logs, and caches.

## Troubleshooting

### Bot Not Responding

```bash
# Check status
patchpal-daemon --status

# Check logs
patchpal-daemon --debug

# Verify token
echo $TELEGRAM_BOT_TOKEN

# Test manually
python -c "
from patchpal.claw.telegram_bot import TelegramBot
bot = TelegramBot('$TELEGRAM_BOT_TOKEN', lambda x,y,z: None)
print('Bot token valid!')
"
```

### Messages Not Stored

```bash
# Check database
sqlite3 ~/.patchpal/messages.db "SELECT * FROM messages LIMIT 5;"

# Check permissions
ls -la ~/.patchpal/messages.db
```

### HEARTBEAT Not Working

```bash
# Enable heartbeat
export HEARTBEAT_ENABLED=true

# Check interval
patchpal-daemon --heartbeat-interval 60  # Every minute (for testing)

# Watch logs
patchpal-daemon --debug 2>&1 | grep -i heartbeat
```

### Multiple Chats Interfering

They shouldn't - each chat is isolated. But if they are:

```bash
# Check sessions
sqlite3 ~/.patchpal/messages.db "SELECT chat_id, COUNT(*) FROM messages GROUP BY chat_id;"

# Verify isolation
ls ~/.patchpal/chats/
```

## Security Considerations

### ✅ What's Secure

- **Bot tokens** stored as env vars (not in code)
- **Per-chat isolation** (conversations don't leak)
- **No eval()** or arbitrary code execution from chat
- **Trigger required** (won't respond to all messages)

### ⚠️ What to Consider

- **Bot token access** - Anyone with token controls bot
- **File system access** - Bot can read/write files (via agent)
- **Command execution** - Bot can run shell commands (via agent)
- **Cost** - Each message = API call to LLM

### 🔒 Best Practices

```bash
# Store tokens securely
cat > ~/.patchpal/.env << EOF
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
DISCORD_BOT_TOKEN=MTA5...
EOF
chmod 600 ~/.patchpal/.env

# Load in daemon
source ~/.patchpal/.env
patchpal-daemon
```

## FAQ

**Q: Can I use both Telegram and Discord at once?**
A: Yes! Set both tokens and the daemon listens to both.

**Q: Do conversations mix between platforms?**
A: No, each chat is isolated with its own session and memory.

**Q: Can I chat from my phone?**
A: Yes! Telegram and Discord both have mobile apps.

**Q: How much does this cost?**
A: Only LLM API costs. ~$0.01 per message with Claude Sonnet.

**Q: Can I turn off HEARTBEAT?**
A: Yes, it's off by default. Only enable with `HEARTBEAT_ENABLED=true`.

**Q: Can multiple people chat with the same bot?**
A: Yes! Each person gets their own isolated session.

**Q: What if I want to clear conversation history?**
A: Delete from database: `rm ~/.patchpal/messages.db` (or delete specific chat rows)

**Q: Can the bot call my scheduled jobs?**
A: Not directly, but it can read job results and trigger new job files.

**Q: Does this replace PatchPal's interactive mode?**
A: No! Interactive mode (`patchpal`) still works. Claw is an additional way to interact.

## Contributing

Ideas for improvements:

- **WhatsApp support** (using baileys library)
- **Voice messages** (transcribe and respond)
- **Image support** (send/receive images)
- **Slack integration**
- **Web dashboard** (view conversations, manage jobs)
- **Multi-user management** (user permissions)

## License

Same as PatchPal (Apache 2.0)
