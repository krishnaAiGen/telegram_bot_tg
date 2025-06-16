# config.py
import json
import os
from dotenv import load_dotenv

load_dotenv()

def load_characters_config(file_path='characters.json'):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CRITICAL ERROR: The '{file_path}' file was not found.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"CRITICAL ERROR: The '{file_path}' file is not valid JSON.")

CHARACTERS_DATA = load_characters_config()

APP_CONFIG = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "firebase_cred_path": os.getenv("FIREBASE_CRED_PATH"),
    "source_channel": os.getenv("TELEGRAM_SOURCE_CHANNEL"),
    "destination_channel": os.getenv("TELEGRAM_DESTINATION_CHANNEL"),
    "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
    "data_dir": "bot_data",
    "chat_classify_model_path": "./trained_model",
    "min_initiate_hours": float(os.getenv("MIN_INITIATE_HOURS", 2.0)),
    "max_initiate_hours": float(os.getenv("MAX_INITIATE_HOURS", 5.0)),
    "min_react_mins": float(os.getenv("MIN_REACT_MINS", 60.0)),
    "max_react_mins": float(os.getenv("MAX_REACT_MINS", 180.0)),
    "min_send_delay_secs": float(os.getenv("MIN_SEND_DELAY_SECS", 60.0)),
    "max_send_delay_secs": float(os.getenv("MAX_SEND_DELAY_SECS", 180.0)),
    "min_convo_bots": 2,
    "max_convo_bots": 10,
}

TELEGRAM_USERS = {}
for char in CHARACTERS_DATA.get("characters", []):
    username = char.get("telegram_user")
    if username:
        env_username = username.upper()
        api_id = os.getenv(f"TELEGRAM_USER_{env_username}_API_ID")
        api_hash = os.getenv(f"TELEGRAM_USER_{env_username}_API_HASH")
        if api_id and api_hash:
            TELEGRAM_USERS[username] = {"api_id": api_id, "api_hash": api_hash}
        else:
            print(f"Warning: Missing API credentials in .env for Telegram user: {username}")

if not APP_CONFIG["openai_api_key"]:
    raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is not set in the .env file.")
if not TELEGRAM_USERS:
    raise ValueError("CRITICAL ERROR: No valid Telegram users configured.")