# config/settings.py
import json
import os
from dotenv import load_dotenv

project_root = os.path.join(os.path.dirname(__file__), '..')
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)

def load_characters_config(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CRITICAL: Character file not found at '{file_path}'.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"CRITICAL: Character file at '{file_path}' is not valid JSON.")

CHARACTERS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'characters.json')
CHARACTERS_DATA = load_characters_config(CHARACTERS_FILE_PATH)

APP_CONFIG = {
    # Core API Configuration
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "firebase_cred_path": os.getenv("FIREBASE_CRED_PATH"),
    "telegram_channel": os.getenv("TELEGRAM_CHANNEL"),
    "data_dir": os.path.join(project_root, 'data'),
    
    # Bot Account Configuration
    "ingestor_bot_user": os.getenv("INGESTOR_BOT_USER", "trial_account"),
    "sender_bot_users": [user.strip() for user in os.getenv("SENDER_BOT_USERS", "trial_account").split(',') if user.strip()],
    "known_bot_ids": [int(bot_id) for bot_id in os.getenv("KNOWN_BOT_IDS", "").split(',') if bot_id.isdigit()],
    
    # Timing Configuration - Response Behavior
    "min_response_delay_secs": float(os.getenv("MIN_REACT_MINS", 0.1)) * 60,    # Convert MIN_REACT_MINS to seconds
    "max_response_delay_secs": float(os.getenv("MAX_REACT_MINS", 1.0)) * 60,    # Convert MAX_REACT_MINS to seconds
    "response_probability": float(os.getenv("RESPONSE_PROBABILITY", 0.3)),      # Default 30% chance to respond
    
    # Timing Configuration - Sending Behavior
    "min_send_delay_secs": float(os.getenv("MIN_SEND_DELAY_SECS", 0.0)),        # From your .env
    "max_send_delay_secs": float(os.getenv("MAX_SEND_DELAY_SECS", 60.0)),       # From your .env
    
    # Timing Configuration - Initiation Behavior
    "min_initiate_hours": float(os.getenv("MIN_INITIATE_HOURS", 0.0)),          # From your .env
    "max_initiate_hours": float(os.getenv("MAX_INITIATE_HOURS", 0.5)),          # From your .env  
    "initiation_check_interval_mins": float(os.getenv("MAX_INITIATE_HOURS", 0.5)) * 60,  # Convert to minutes
    
    # Memory Configuration
    "max_recent_messages": int(os.getenv("MAX_RECENT_MESSAGES", 1000)),             # Max messages to remember
    "max_sent_messages_cache": int(os.getenv("MAX_SENT_MESSAGES_CACHE", 20)),       # Max sent messages to track
    
    # OpenAI Configuration
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),                       # OpenAI model to use
    "openai_max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", 150)),                  # Max tokens per response
    "openai_temperature": float(os.getenv("OPENAI_TEMPERATURE", 0.8)),              # Response creativity (0.0-2.0)
}

TELEGRAM_USERS = {}
all_bot_usernames = [APP_CONFIG["ingestor_bot_user"]] + APP_CONFIG["sender_bot_users"]

for username in set(filter(None, all_bot_usernames)):
    env_var_prefix = f"TELEGRAM_USER_{username}_"
    api_id = os.getenv(f"{env_var_prefix}API_ID")
    api_hash = os.getenv(f"{env_var_prefix}API_HASH")
    if api_id and api_hash:
        TELEGRAM_USERS[username] = {"api_id": api_id, "api_hash": api_hash}
    else:
        print(f"Warning: Missing API credentials for Telegram user: {username}")

if not APP_CONFIG["openai_api_key"]:
    raise ValueError("CRITICAL: OPENAI_API_KEY is not set in the .env file.")
if not APP_CONFIG["ingestor_bot_user"] or not APP_CONFIG["sender_bot_users"]:
    raise ValueError("CRITICAL: INGESTOR_BOT_USER and SENDER_BOT_USERS must be set in .env")
if APP_CONFIG["ingestor_bot_user"] not in TELEGRAM_USERS:
    raise ValueError(f"CRITICAL: Credentials for ingestor '{APP_CONFIG['ingestor_bot_user']}' are missing.")
for user in APP_CONFIG["sender_bot_users"]:
    if user not in TELEGRAM_USERS:
        raise ValueError(f"CRITICAL: Credentials for sender '{user}' are missing.")

print("Configuration loaded successfully.")