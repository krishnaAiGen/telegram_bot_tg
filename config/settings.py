# config/settings.py
import json
import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This robustly finds the .env file at the project root.
project_root = os.path.join(os.path.dirname(__file__), '..')
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    # Fallback for environments where the .env file might be in the current working directory
    load_dotenv()

def load_characters_config(file_path: str):
    """Loads and validates the character definitions from the JSON file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CRITICAL ERROR: The character definition file was not found at '{file_path}'.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"CRITICAL ERROR: The character file at '{file_path}' is not valid JSON.")

# --- Application-wide Configurations ---

# Define the path to the characters file, relative to this settings file.
CHARACTERS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'characters.json')
CHARACTERS_DATA = load_characters_config(CHARACTERS_FILE_PATH)

# A central dictionary for all application settings, sourced from the environment with sensible defaults.
APP_CONFIG = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "firebase_cred_path": os.getenv("FIREBASE_CRED_PATH"),
    "source_channel": os.getenv("TELEGRAM_SOURCE_CHANNEL"),
    "destination_channel": os.getenv("TELEGRAM_DESTINATION_CHANNEL"),
    "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
    "known_bot_ids": [int(bot_id) for bot_id in os.getenv("KNOWN_BOT_IDS", "").split(',') if bot_id.isdigit()],

    
    # The data directory will be in the project root.
    "data_dir": os.path.join(project_root, 'data'),
    
    # Timing and behavior settings with defaults.
        
    "min_initiate_hours": float(os.getenv("MIN_INITIATE_HOURS", 2.0)),
    "max_initiate_hours": float(os.getenv("MAX_INITIATE_HOURS", 5.0)),
    "min_react_mins": float(os.getenv("MIN_REACT_MINS", 60.0)),
    "max_react_mins": float(os.getenv("MAX_REACT_MINS", 180.0)),
    "min_send_delay_secs": float(os.getenv("MIN_SEND_DELAY_SECS", 60.0)),
    "max_send_delay_secs": float(os.getenv("MAX_SEND_DELAY_SECS", 180.0)),
    
    # --- MODIFIED LINES ---
    "min_convo_bots": int(os.getenv("MIN_CONVO_BOTS", 2)),
    "max_convo_bots": int(os.getenv("MAX_CONVO_BOTS", 10)),
}

# Dynamically build the Telegram client configuration from .env based on characters.json
TELEGRAM_USERS = {}
for char in CHARACTERS_DATA.get("characters", []):
    username = char.get("telegram_user")
    if username:
        # No more .upper(), just use the name directly
        env_var_prefix = f"TELEGRAM_USER_{username}_"
        api_id = os.getenv(f"{env_var_prefix}API_ID")
        api_hash = os.getenv(f"{env_var_prefix}API_HASH")
        if api_id and api_hash:
            TELEGRAM_USERS[username] = {"api_id": api_id, "api_hash": api_hash}
        else:
            print(f"Warning: Missing API credentials in .env for Telegram user: {username} (looked for {env_var_prefix}API_ID/HASH)")
# --- Startup Validation ---
# The application will fail to start if these critical configurations are missing.
if not APP_CONFIG["openai_api_key"]:
    raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is not set in the .env file.")
if not TELEGRAM_USERS:
    raise ValueError("CRITICAL ERROR: No valid Telegram users could be configured from .env. Check your TELEGRAM_USER_* variables and characters.json.")