# Telegram Bot Workflow Documentation

## Overview
This document provides a comprehensive breakdown of the AI-powered Telegram bot system that simulates multiple personas having realistic conversations in Telegram channels.

## System Architecture

### Three-Process Architecture
The bot operates using three independent processes that communicate via shared JSON state files:

1. **"The Ears" - Data Ingestor** (`telegram.py`)
2. **"The Brain" - Main Logic Loop** (`response.py`) 
3. **"The Mouth" - Message Sender** (`telegram_utils.py`)

### Process Communication
- **Method**: Shared JSON state files (no direct IPC)
- **State Directory**: `data/` folder contains all persistent state
- **Atomic Operations**: File-based operations ensure data consistency

## 1. Message Fetching Logic

### Data Ingestion Process (`telegram.py`)

#### Initial Setup
- **Database**: Firebase Firestore collections named `conversation_ai_{channel_name}`
- **Message Structure**: 
  ```json
  {
    "message_id": 12345,
    "text": "message content",
    "sender_id": 987654321,
    "date": "2024-01-01T12:00:00Z"
  }
  ```

#### Fetching Strategy
1. **First Run**: Complete history fetch using batched operations
   - **Batch Size**: 499 messages per batch (Firestore limit: 500)
   - **Flag File**: Creates `fetch_and_save_done.txt` to prevent re-fetching
   - **Process**: Iterates through entire channel history using `client.iter_messages()`

2. **Ongoing Operation**: Real-time message listening
   - **Event Handler**: `@client.on(events.NewMessage())`
   - **Auto-save**: New messages immediately saved to Firestore

#### Message Retrieval Functions
- **`get_last_message()`**: Fetches most recent single message
- **`get_last_100_message_texts()`**: Fetches last 100 messages for context generation

## 2. Decision Making Logic (`response.py`)

### Main Loop Cycle
The brain runs an endless loop with these steps:

1. **Fetch Latest Message**
2. **Calculate Time Differences** 
3. **Make Decision**: React, Initiate, or Wait
4. **Execute Action**
5. **Process Scheduled Messages**
6. **Sleep** (15-30 minutes randomly)

### Decision Thresholds

#### Reaction Logic
```python
react_thresh = timedelta(minutes=random.uniform(60.0, 180.0))
if time_since > react_thresh and not has_reacted(message):
    trigger_reaction()
```
- **Trigger**: Message is 60-180 minutes old
- **Condition**: Bot hasn't already reacted to this specific message
- **Tracking**: Reactions logged in `multiple_check.json`

#### Initiation Logic  
```python
init_thresh = timedelta(hours=random.uniform(2.0, 5.0))
if time_since > init_thresh:
    trigger_initiation()
```
- **Trigger**: Last message is 2-5 hours old
- **Purpose**: Revive quiet channels with new conversations

## 3. Persona Selection Logic (`llm_personas.py`)

### Semantic Similarity Matching
Uses SentenceTransformer model `all-MiniLM-L6-v2` for persona selection:

```python
# 1. Encode incoming message
message_embedding = sim_model.encode(message, convert_to_tensor=True)

# 2. Calculate similarities with all personas
similarities = {
    name: util.pytorch_cos_sim(message_embedding, persona_embedding).item()
    for name, persona_embedding in persona_embeddings.items()
}

# 3. Select best match
best_persona = max(similarities, key=similarities.get)
```

### Selection Process
1. **Encode** message into vector representation
2. **Compare** with pre-computed persona description embeddings
3. **Calculate** cosine similarity scores
4. **Select** persona with highest similarity (threshold: 0.2)
5. **Fallback** to random persona if no good match

### Persona Structure
Each persona contains:
- `persona_name`: Unique identifier
- `description`: Detailed personality description
- `character_name`: Parent character group
- `telegram_user`: Associated Telegram account

## 4. Response Generation Types

### A. Reaction Responses

#### Process Flow
1. **Memory Retrieval**: Get user's conversation history (max 15 turns = 30 messages)
2. **Memory Management**: If full, keep last 10 turns (20 messages)
3. **Persona Selection**: Use semantic similarity matching
4. **Message Classification**: Classify as 'crypto' or 'human' using RoBERTa model
5. **Response Generation**:
   - **'human'**: Generic human-like reply
   - **'crypto'**: Persona-specific contextual response
6. **Safety Check**: OpenAI moderation API screening
7. **Memory Update**: Add response to conversation history
8. **Queue Message**: Add to send queue with persona's Telegram account

#### Memory Format
```python
history = [
    {"role": "user", "content": "user message"},
    {"role": "assistant", "content": "bot response"},
    # ... up to 30 messages total
]
```

### B. Initiation Responses

#### Multi-Bot Conversation Planning
1. **Topic Generation**: 
   - Analyze last 100 messages for context
   - Generate new discussion topic using LLM
   - Check against recent topics to avoid repetition

2. **Bot Selection**:
   - Choose 2-10 random personas using numeric indices
   - Load from `personas.json` mapping file

3. **Time Distribution**:
   - **50%** of bots respond in 5-720 minutes
   - **30%** of bots respond in 720-1080 minutes  
   - **20%** of bots respond in 1080-1440 minutes

4. **Response Generation**:
   - Each persona generates topic-specific response
   - Responses are 20-50 words with/without emojis
   - Personas don't reveal their identity

5. **Scheduling**:
   - Create timestamp-based schedule in `time_persona.json`
   - Messages queued when their time arrives

#### Conversation Dictionary Structure
```python
conversation_dict = {
    "persona_name": {
        time_in_minutes: "generated_response"
    }
}
```

### C. Random Talk Responses

#### Scheduled Random Conversations
- **Frequency**: Hourly scheduled talks
- **Schedule Generation**: Creates 5 timestamps with 16+ hour gaps
- **Content Types**:
  1. **Greetings**: "Warm friendly message within 10 words"
  2. **Queries**: Persona asks question in 20-40 words  
  3. **Discussion Topics**: Persona raises topic for discussion

#### Implementation
```python
random_content_dict = {
    "1": "greetings", 
    "2": "queries", 
    "3": "discussion topic"
}
content_type = random_content_dict[str(random.randint(1, 3))]
```

### D. Scheduled Responses

#### Time-Based Message Delivery
- **Source**: From initiation planning and random talks
- **Check Frequency**: Every main loop cycle
- **Process**: Compare current time with scheduled timestamps
- **Action**: Queue messages when time arrives
- **Cleanup**: Remove sent messages from schedule

## 5. Message Classification (`classify_chat.py`)

### RoBERTa-Based Classification
- **Model**: Fine-tuned RoBERTa transformer
- **Categories**: 'crypto' vs 'human'
- **Purpose**: Determines response generation strategy

#### Classification Process
```python
# 1. Tokenization
encodings = tokenizer(text, truncation=True, padding=True, max_length=128)

# 2. Model Inference  
with torch.no_grad():
    outputs = model(**encodings)
    logits = outputs.logits
    
# 3. Probability Calculation
probs = F.softmax(logits, dim=-1)
prediction_idx = torch.argmax(probs, dim=-1).item()

# 4. Label Mapping
label_mapping = {0: 'crypto', 1: 'human'}
prediction = label_mapping[prediction_idx]
```

## 6. Message Sending Logic (`telegram_utils.py`)

### Queue-Based Sending System

#### Message Queue Structure
```python
message_obj = {
    "message": "response text",
    "telegram_user": "persona_telegram_account"  # Can be None
}
```

#### Sending Process
1. **Queue Check**: Continuously monitor `message_queue.json`
2. **Account Selection**: 
   - Use specified Telegram account for persona
   - Fallback to random account if not available
3. **Human Simulation**:
   - Show "typing" indicator for 3-7 seconds
   - Send message to destination channel
4. **Delay Management**: Wait 60-180 seconds before next message
5. **Error Handling**: Re-queue failed messages

#### Client Management
```python
clients = {
    user: TelegramClient(user, api_id, api_hash)
    for user, config in TELEGRAM_USERS.items()
}
```

### Realistic Behavior Simulation
- **Typing Indicators**: `client.action(channel, 'typing')`
- **Variable Delays**: Random intervals between all actions
- **Connection Management**: Connect/disconnect for each message

## 7. State Management (`utils.py`)

### StateManager Class
Centralized management of all persistent state files:

#### State Files
- `discussed_topic.json`: Recently discussed topics
- `message_queue.json`: Pending messages to send
- `multiple_check.json`: Reaction tracking (prevents duplicates)
- `conversation_memory.json`: Per-user conversation history
- `time_persona.json`: Scheduled conversation timestamps
- `random_conversation_time.json`: Random talk schedule
- `persona_assignments.json`: Persona-user mappings
- `clean_bot.json`: Bot message cleanup counter

#### Key Methods
```python
# Memory Management
get_user_memory(user_id) -> list
update_user_memory(user_id, history)

# Queue Operations  
add_message_to_queue(message_obj)
get_message_from_queue() -> dict

# Schedule Management
save_initiation_schedule(conversation_dict)
```

## 8. Content Safety Logic

### Multi-Layer Safety System

#### OpenAI Moderation
```python
async def is_content_offensive(text: str) -> bool:
    response = await openai.Moderation.acreate(input=text)
    return response.results[0].flagged
```

#### Safety Process
1. **Pre-Send Check**: All responses screened before queuing
2. **Blocking**: Offensive content discarded, not sent
3. **Logging**: Violations logged for monitoring
4. **No Retry**: Blocked messages not re-queued

## 9. Error Handling and Monitoring

### Comprehensive Error Management

#### Slack Integration
- **Critical Errors**: Posted to Slack webhook
- **Error Context**: Full traceback included
- **Non-Blocking**: Errors don't crash the system

#### Recovery Mechanisms
- **Graceful Degradation**: Failed operations skip gracefully
- **Retry Logic**: Failed messages re-queued for later attempts
- **State Persistence**: All state survives process restarts
- **Process Isolation**: One process failure doesn't affect others

#### Error Handling Pattern
```python
try:
    # Main operation
    await perform_action()
except Exception as e:
    error_trace = traceback.format_exc()
    await post_error_to_slack(error_trace)
    await asyncio.sleep(60 * 10)  # Wait before retry
```

## 10. Configuration Management (`config.py`)

### Environment-Based Configuration

#### Required Environment Variables
```bash
# OpenAI
OPENAI_API_KEY="sk-..."

# Firebase  
FIREBASE_CRED_PATH="/path/to/firebase-credentials.json"

# Telegram Channels
TELEGRAM_SOURCE_CHANNEL="channel_to_listen"
TELEGRAM_DESTINATION_CHANNEL="channel_to_send"

# Telegram Accounts (per persona)
TELEGRAM_USER_USERNAME_API_ID="12345678"
TELEGRAM_USER_USERNAME_API_HASH="api_hash"
```

#### Dynamic Configuration Loading
- **Character Data**: Loaded from `character.json`
- **Telegram Users**: Built dynamically from environment variables
- **Validation**: Startup checks ensure all required config present

## 11. Timing and Randomization

### Realistic Human Behavior Patterns

#### Randomized Intervals
- **Main Loop**: 15-30 minute sleep cycles
- **Reaction Timing**: 60-180 minutes after message
- **Initiation Timing**: 2-5 hours of inactivity
- **Send Delays**: 60-180 seconds between messages
- **Typing Duration**: 3-7 seconds

#### Time Distribution Strategy
```python
# Conversation participation timing
percentages = [0.5, 0.3, 0.2]  # Early, middle, late responders
timeframes = [(5, 720), (720, 1080), (1080, 1440)]  # Minutes
```

## 12. Persona System

### Character Hierarchy
```
Characters (4 total)
├── The Analyst (JoiN9911)
│   ├── Crypto OG
│   ├── Market Analyst  
│   ├── Token Economist
│   └── Venture Capitalist
├── The Builder (davethm)
│   ├── Tech Developer
│   ├── DeFi Advocate
│   ├── Product Evangelist
│   └── Security Expert
├── The Community Voice (devtoye)
│   ├── The Enthusiast
│   ├── Artist
│   ├── Community Builder
│   └── The Gamer
└── The Contrarian (JoiN9911)
    ├── The Skeptic
    └── Regulation Expert
```

### Persona Attributes
Each persona has:
- **Unique Personality**: Detailed behavioral description
- **Expertise Area**: Specific knowledge domain
- **Communication Style**: Tone, vocabulary, emoji usage
- **Telegram Account**: Associated sending account

## 13. Startup and Execution

### Launch Process (`main.py`)
```python
PROCESSES_TO_RUN = [
    "telegram.py",        # Data Ingestor
    "response.py",        # Main Logic  
    "telegram_utils.py"   # Message Sender
]
```

#### Process Management
1. **Parallel Launch**: All processes start simultaneously
2. **Process Monitoring**: Track PIDs and status
3. **Graceful Shutdown**: Ctrl+C terminates all processes
4. **Error Isolation**: Individual process failures don't affect others

### Dependencies Installation
```bash
pip install python-dotenv google-cloud-firestore firebase-admin torch transformers sentence-transformers numpy pandas aiohttp telethon pytz
```

## 14. Data Flow Summary

```
Telegram Channel → Data Ingestor → Firestore Database
                                        ↓
State Files ← Main Logic Loop ← Database Query
     ↓
Message Queue → Message Sender → Telegram Channel
```

### Complete Workflow Cycle
1. **Listen**: Data ingestor saves new messages to database
2. **Analyze**: Main logic fetches latest message and calculates timing
3. **Decide**: Determine whether to react, initiate, or wait
4. **Generate**: Create appropriate response using selected persona
5. **Validate**: Check content safety and appropriateness
6. **Queue**: Add message to send queue with persona account
7. **Send**: Message sender delivers to destination channel
8. **Track**: Update state files to prevent duplicates
9. **Repeat**: Return to step 1

This system creates the illusion of multiple human participants having natural, engaging conversations while maintaining realistic timing patterns and avoiding repetitive or inappropriate content. 