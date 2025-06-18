# src/services/utils.py
import json
import os
from datetime import datetime
import pytz

# This file now contains simple, standalone helper functions for file operations.
# This prevents different processes from sharing a complex StateManager object,
# which was causing file access conflicts.

def get_data_dir(config):
    """Gets the data directory path from the central config and ensures it exists."""
    data_dir = config['data_dir']
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def load_json(file_path: str):
    """
    Safely loads a JSON file.
    Returns a list for files expected to be queues, and a dictionary otherwise.
    Creates the file with a default value if it doesn't exist.
    """
    if not os.path.exists(file_path):
        # Create the file with a sensible default if it's missing
        default_content = [] if 'queue' in os.path.basename(file_path) else {}
        save_json(file_path, default_content)
        return default_content
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                return [] if 'queue' in os.path.basename(file_path) else {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        # Fallback in case of corruption or race condition
        return [] if 'queue' in os.path.basename(file_path) else {}

def save_json(file_path: str, data):
    """Safely saves data to a JSON file with human-readable formatting."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving JSON to {file_path}: {e}")


def get_ist_time_str() -> str:
    """Returns the current time in the IST timezone as a formatted string."""
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')