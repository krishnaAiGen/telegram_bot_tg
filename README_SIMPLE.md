# Simple Telegram Bot 🤖

A **dramatically simplified** version of the original complex Telegram bot. Same functionality, **90% less code**.

## What It Does

1. **Listens** to messages in a Telegram channel
2. **Responds** using AI personas (30% response rate)
3. **Initiates** conversations when the channel is quiet
4. **Multiple personas** for variety

## Key Improvements ✅

- ✅ **Single file** instead of complex architecture
- ✅ **No file-based state** - everything in memory
- ✅ **No race conditions** - simple sequential processing
- ✅ **No worker queues** - direct async handling  
- ✅ **Easy to debug** - all logic in one place
- ✅ **Fewer dependencies** - only 3 packages needed

## Quick Setup

### 1. Install Dependencies
```bash
pip install -r simple_requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run Bot
```bash
python simple_bot.py
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | Your OpenAI API key | ✅ Yes |
| `TELEGRAM_CHANNEL` | Channel name (without @) | ✅ Yes |
| `TELEGRAM_USER_ACCOUNT1_API_ID` | Telegram API ID | ✅ Yes |
| `TELEGRAM_USER_ACCOUNT1_API_HASH` | Telegram API Hash | ✅ Yes |
| `INITIATE_AFTER_HOURS` | Hours of silence before initiating | ❌ No (default: 3) |
| `KNOWN_BOT_IDS` | Bot IDs to ignore (comma-separated) | ❌ No |

## Architecture Comparison

### Old Complex Version:
- 6+ files, multiple modules
- 3 worker processes with queues
- File-based state management
- Race conditions and debugging nightmares
- Firebase dependency

### New Simple Version:
- **1 file** - `simple_bot.py`
- **Direct async** - no workers/queues
- **In-memory state** - no file I/O
- **Zero race conditions**
- **No external databases**

## How It Works

```python
# The entire bot logic:
1. Listen to new messages
2. Skip if it's our own message or from bots
3. 30% chance to respond after random delay
4. Generate response using random persona
5. Send response
6. If quiet for 3+ hours, initiate conversation
```

## Monitoring

The bot provides clear emoji-based logging:
- 🚀 Starting up
- 📨 New message received  
- 🎯 Deciding to respond
- ⏰ Waiting before response
- 🎭 Using specific persona
- 📤 Message sent
- 💡 Initiating conversation
- ❌ Errors

## Troubleshooting

### Bot Not Responding
1. Check OpenAI API key is valid
2. Verify Telegram credentials
3. Ensure bot accounts are in the channel

### Rate Limits
- OpenAI: Bot includes delays between requests
- Telegram: Random delays prevent hitting limits

### Memory Usage
- `recently_processed` limited to 1000 messages
- `recently_sent` limited to 20 messages
- Automatic cleanup prevents memory leaks

## Migration from Complex Version

Replace your complex setup with:
```bash
# Old way
python src/main.py

# New way  
python simple_bot.py
```

Same functionality, **dramatically simpler**! 