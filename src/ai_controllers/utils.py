# src/ai_controllers/utils.py
import json
import os
import pickle
from datetime import datetime, timedelta
import pytz
from config import APP_CONFIG

class StateManager:
    """Manages all file-based state for the application in a safe, central location."""
    def __init__(self):
        self.data_dir = APP_CONFIG['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Define paths for all state files
        self.discussed_topics_file = os.path.join(self.data_dir, 'discussed_topic.json')
        self.message_queue_file = os.path.join(self.data_dir, 'message_queue.json')
        self.reaction_log_file = os.path.join(self.data_dir, 'multiple_check.json')
        self.error_file = os.path.join(self.data_dir, 'error.json')
        self.assignments_file = os.path.join(self.data_dir, 'persona_assignments.json')
        self.memory_file = os.path.join(self.data_dir, 'conversation_memory.json')
        self.initiation_schedule_file = os.path.join(self.data_dir, 'time_persona.json')
        self.random_talk_schedule_file = os.path.join(self.data_dir, 'random_conversation_time.json')
        self.clean_bot_state_file = os.path.join(self.data_dir, 'clean_bot.json')
        
        # Ensure all state files exist on startup
        self._init_json_file(self.discussed_topics_file, {})
        self._init_json_file(self.message_queue_file, [])
        self._init_json_file(self.reaction_log_file, {})
        self._init_json_file(self.error_file, {})
        self._init_json_file(self.assignments_file, {})
        self._init_json_file(self.memory_file, {})
        self._init_json_file(self.initiation_schedule_file, {})
        self._init_json_file(self.random_talk_schedule_file, [])
        self._init_json_file(self.clean_bot_state_file, {"counter": 10})

    def _init_json_file(self, file_path, default_content):
        if not os.path.exists(file_path):
            self.save_json(file_path, default_content)

    def load_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return [] if 'queue' in file_path or 'time' in file_path else {}

    def save_json(self, file_path, data):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    def save_initiation_schedule(self, conversation_dict: dict):
        """Creates a timestamp-based schedule from a planned conversation."""
        schedule = {}
        now = datetime.now()
        sorted_convo = sorted(conversation_dict.items(), key=lambda x: list(x[1].keys())[0])

        for persona_name, time_msg_dict in sorted_convo:
            minutes_to_add = list(time_msg_dict.keys())[0]
            message_text = list(time_msg_dict.values())[0]
            
            future_time = now + timedelta(minutes=minutes_to_add)
            schedule_key = future_time.strftime("%Y-%m-%d %H:%M:%S")
            schedule[schedule_key] = [persona_name, message_text]
            now = future_time

        self.save_json(self.initiation_schedule_file, schedule)
        print("Initiation conversation schedule saved.")
            
    def get_user_memory(self, user_id: str) -> list:
        all_memory = self.load_json(self.memory_file)
        return all_memory.get(user_id, [])

    def update_user_memory(self, user_id: str, history: list):
        all_memory = self.load_json(self.memory_file)
        all_memory[user_id] = history
        self.save_json(self.memory_file, all_memory)

    def add_message_to_queue(self, message: dict):
        queue = self.load_json(self.message_queue_file)
        queue.append(message)
        self.save_json(self.message_queue_file, queue)

    def get_message_from_queue(self) -> dict | None:
        queue = self.load_json(self.message_queue_file)
        if not queue: return None
        return queue.pop(0)

    def save_error(self, error_traceback: str):
        errors = self.load_json(self.error_file)
        errors[get_ist_time()] = error_traceback
        self.save_json(self.error_file, errors)

# Kept for backward compatibility
def save_dictionary(dictionary, filename):
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(dictionary, json_file, indent=4)

def load_dictionary(filename):
    with open(filename, 'r', encoding='utf-8') as json_file:
        return json.load(json_file)

def save_list(lst, filename):
    with open(filename, 'wb') as file: pickle.dump(lst, file)

def load_list(filename):
    with open(filename, 'rb') as file: return pickle.load(file)

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')