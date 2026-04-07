# PatchPal Claw - Automation Examples

Examples showing how to use PatchPal Claw as a general AI assistant with scheduled automation and chat bot capabilities.

## Quick Start

See [patchpal/claw/README.md](../../patchpal/claw/README.md) for full documentation.

```bash
# 1. Install
pip install patchpal[claw]

# 2. Setup bot
export TELEGRAM_BOT_TOKEN="..."

# 3. Start daemon
patchpal-daemon

# 4. Chat with bot
# Telegram: "@patchpal hello"
```

## Job Examples

### Reddit Listening

```yaml
# ~/.patchpal/jobs/reddit-listening.yaml
schedule: "*/15 * * * *"
enabled: true
notify: true  # Sends to all active chats
prompt: |
  Run the reddit search script:
  run_shell python ~/.patchpal/scripts/reddit_search.py "AI agents"

  Analyze top 3 posts and summarize interesting discussions.
```

When this runs, result goes to your Telegram/Discord chat!

### Daily Summary

```yaml
# ~/.patchpal/jobs/daily-summary.yaml
schedule: "0 18 * * *"  # 6 PM daily
enabled: true
notify: true
prompt: |
  Review today's automation activity:
  - Check job logs
  - Review cache for interesting findings
  - Summarize key events

  Keep it brief and casual.
```

You'll get a daily summary in your chat at 6 PM.

### LinkedIn Enrichment

```yaml
# ~/.patchpal/jobs/linkedin-enrichment.yaml
schedule: "0 9 * * 1"  # Monday 9 AM
enabled: true
notify: true
prompt: |
  Run LinkedIn search for founders:
  run_shell python ~/.patchpal/scripts/linkedin_search.py "AI startup founder"

  Filter for interesting profiles and provide summary.
```

## Conversation Examples

Beyond scheduled jobs, you can have conversations with your assistant:

### Ask About Job Results

```
You: @patchpal what did the reddit job find today?
Bot: Today's reddit search found 3 posts:
     1. Discussion about AI agent frameworks
     2. New research on LangChain alternatives
     3. Tutorial on building coding assistants

     The framework discussion was most interesting...
```

### Set Reminders

```
You: @patchpal remind me to review those LinkedIn profiles tomorrow at 10am
Bot: Got it! I'll remind you tomorrow at 10am to review the LinkedIn profiles.

[Next day at 10am, HEARTBEAT runs]
Bot: hey, it's 10am - time to review those linkedin profiles from yesterday
```

### Check Automation Status

```
You: @patchpal how are the jobs doing?
Bot: Let me check...

     Active jobs:
     - reddit-listening: Last run 12 minutes ago (success)
     - daily-summary: Runs at 6 PM (3 hours from now)
     - linkedin-enrichment: Runs Monday 9 AM (2 days away)

     All jobs healthy!
```

### On-Demand Execution

```
You: @patchpal run the reddit search now
Bot: Running reddit search...
     [executes script]

     Found 2 new posts:
     1. "Building AI agents with Claude" (85 upvotes)
     2. "Agent frameworks comparison" (42 upvotes)
```

## Scripts

### reddit_search.py

Located in `scripts/reddit_search.py` - searches Reddit and uses cache to deduplicate.

**Usage in job:**
```yaml
prompt: |
  run_shell python ~/.patchpal/scripts/reddit_search.py "AI agents"
```

**Usage in conversation:**
```
You: @patchpal search reddit for "coding assistants"
Bot: [runs script via agent] Found 5 posts...
```

### linkedin_search.py

Located in `scripts/linkedin_search.py` - demonstrates API interception pattern.

**Usage in job:**
```yaml
prompt: |
  run_shell python ~/.patchpal/scripts/linkedin_search.py "AI startup founder"
```

**Usage in conversation:**
```
You: @patchpal find 3 AI startup founders on linkedin
Bot: [runs script] Found profiles:
     1. John Doe - Founded AI startup in 2023...
     2. Jane Smith - CEO of ML platform...
     3. Bob Wilson - Serial founder in AI space...
```

## HEARTBEAT Examples

HEARTBEAT is the proactive monitoring feature (optional).

### Enable HEARTBEAT

```bash
export HEARTBEAT_ENABLED=true
patchpal-daemon --heartbeat-interval 900  # Every 15 minutes
```

### HEARTBEAT Behavior

Every 15 minutes, checks all conversations and asks:
- "Are there any pending tasks or reminders?"
- "Did the user ask me to follow up on something?"
- "Is there anything time-sensitive?"

If yes: Sends casual reminder
If no: Stays silent

### Example HEARTBEAT Interaction

```
Morning:
You: @patchpal remind me to deploy the app this afternoon
Bot: Got it, I'll remind you this afternoon to deploy the app.

[Afternoon, HEARTBEAT runs]
Bot: hey, you wanted to deploy the app this afternoon - still planning to?

You: yes, doing it now
Bot: Cool, let me know if you need help!
```

## File Organization

```
examples/automation/
├── README.md (this file)
├── jobs/ (example job definitions)
│   ├── reddit-listening.yaml
│   ├── linkedin-enrichment.yaml
│   └── daily-summary.yaml
└── scripts/ (example scripts)
    ├── reddit_search.py
    └── linkedin_search.py

~/.patchpal/ (your setup)
├── jobs/ (copy examples here)
├── scripts/ (copy examples here)
├── cache/ (job caches)
├── messages.db (conversation storage)
└── chats/ (per-chat memory files)
```

## Common Use Cases

### Daily automation + on-demand queries

Set up a job that runs daily:
```yaml
schedule: "0 9 * * *"
notify: true
```

Then query it anytime:
```
You: @patchpal what did the morning job find?
Bot: [accesses job results and summarizes]
```

### Scheduled + manual execution

Set up weekly automation:
```yaml
schedule: "0 9 * * 1"  # Monday mornings
```

But run it immediately when needed:
```
You: @patchpal run the linkedin search right now
Bot: [executes immediately]
```

### Automation + reminders

Job finds something interesting → notifies you:
```
Bot: Found 5 new AI startups in today's search!

You: @patchpal remind me to research these tomorrow
Bot: Got it, I'll remind you tomorrow.

[Next day, HEARTBEAT]
Bot: hey, you wanted to research those AI startups from yesterday
```

## Tips

### Best Practices

1. **Start simple** - Get bot working first, then add jobs
2. **Use trigger word** - Default `@patchpal` prevents spam
3. **Enable HEARTBEAT cautiously** - It messages you proactively
4. **Per-chat isolation** - Each chat has its own conversation context
5. **Check status often** - `patchpal-daemon --status` shows health

### Common Patterns

**Information gathering:**
- Jobs collect data (Reddit, LinkedIn, etc.)
- You query via chat: "@patchpal what did you find today?"
- Bot summarizes with full context

**Task management:**
- You set reminders in conversation
- HEARTBEAT proactively reminds you
- Natural language: "remind me to X tomorrow at 2pm"

**On-demand execution:**
- Jobs run on schedule
- But you can trigger manually: "@patchpal run X now"
- Best of both worlds

## Further Reading

- [PatchPal Claw README](../../patchpal/claw/README.md) - Full documentation
- [Job Scheduler](../../patchpal/claw/scheduler.py) - How jobs work
- [Session Manager](../../patchpal/claw/session_manager.py) - How context works
- [Message Store](../../patchpal/claw/message_store.py) - How messages stored

## Troubleshooting

**Check status:**
```bash
patchpal-daemon --status
```

**Debug mode:**
```bash
patchpal-daemon --debug
```

**Test bot:**
```bash
python -c "
from patchpal.claw.telegram_bot import TelegramBot
bot = TelegramBot('$TELEGRAM_BOT_TOKEN', lambda x,y,z: print(f'Got message: {y}'))
print('Bot created successfully!')
"
```

**Check messages:**
```bash
sqlite3 ~/.patchpal/messages.db "SELECT chat_id, role, content FROM messages ORDER BY timestamp DESC LIMIT 10;"
```

## What's Next?

Ideas for extending your setup:

1. **Add more jobs** - Weather checks, news summaries, system monitoring
2. **Create custom scripts** - Integrate with your tools and APIs
3. **Multiple chats** - Different contexts (work vs personal)
4. **Team usage** - Share bot with team members (each gets own session)
5. **Advanced automation** - Combine multiple jobs, chain workflows

---

**Questions?** See [patchpal/claw/README.md](../../patchpal/claw/README.md) for complete documentation.
