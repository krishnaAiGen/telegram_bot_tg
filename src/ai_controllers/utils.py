# utils.py
import json
import os
from datetime import datetime
import pytz

class StateManager:
    """Manages all file-based state for the application in a safe, central location."""
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.discussed_topics_file = os.path.join(data_dir, 'discussed_topic.json')
        self.message_queue_file = os.path.join(data_dir, 'polkassembly_message.txt')
        self.reaction_log_file = os.path.join(data_dir, 'multiple_check.json')
        self.error_file = os.path.join(data_dir, 'error.json')
        
        self._init_json_file(self.discussed_topics_file, {})
        self._init_json_file(self.message_queue_file, [])
        self._init_json_file(self.reaction_log_file, {})
        self._init_json_file(self.error_file, {})

    def _init_json_file(self, file_path, default_content):
        if not os.path.exists(file_path):
            self.save_json(file_path, default_content)

    def load_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return [] if 'polkassembly_message' in file_path else {}

    def save_json(self, file_path, data):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def add_message_to_queue(self, message: str):
        queue = self.load_json(self.message_queue_file)
        queue.append(message)
        self.save_json(self.message_queue_file, queue)

    def get_message_from_queue(self) -> str | None:
        queue = self.load_json(self.message_queue_file)
        if not queue:
            return None
        message = queue.pop(0)
        self.save_json(self.message_queue_file, queue)
        return message

    def is_topic_discussed(self, topic: str) -> bool:
        discussed = self.load_json(self.discussed_topics_file)
        return topic.lower() in [v.lower() for v in discussed.values()]

    def save_discussed_topic(self, topic: str):
        discussed = self.load_json(self.discussed_topics_file)
        discussed[get_ist_time()] = topic
        self.save_json(self.discussed_topics_file, discussed)

    def has_reacted(self, message_text: str) -> bool:
        log = self.load_json(self.reaction_log_file)
        return message_text in log

    def log_reaction(self, message_text: str):
        log = self.load_json(self.reaction_log_file)
        log[message_text] = log.get(message_text, 0) + 1
        self.save_json(self.reaction_log_file, log)

    def save_error(self, error_traceback: str):
        errors = self.load_json(self.error_file)
        errors[get_ist_time()] = error_traceback
        self.save_json(self.error_file, errors)
        print(f"Error saved to {self.error_file}")

def get_ist_time():
    ist_timezone = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist_timezone).strftime('%Y-%m-%d %H:%M:%S')