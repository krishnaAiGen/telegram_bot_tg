# src/services/utils.py
import json
import os
import pickle
from datetime import datetime, timedelta
import pytz

# Import the centralized config object
from config.settings import APP_CONFIG

class StateManager:
    """Manages all file-based state for the application in a safe, central location."""
    def __init__(self):
        self.data_dir = APP_CONFIG['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.discussed_topics_file = os.path.join(self.data_dir, 'discussed_topic.json')
        self.message_queue_file = os.path.join(self.data_dir, 'message_queue.json')
        self.reaction_log_file = os.path.join(self.data_dir, 'multiple_check.json') # This is the file we'll use
        self.error_file = os.path.join(self.data_dir, 'error.json')
        self.assignments_file = os.path.join(self.data_dir, 'persona_assignments.json')
        self.memory_file = os.path.join(self.data_dir, 'conversation_memory.json')
        self.initiation_schedule_file = os.path.join(self.data_dir, 'time_persona.json')
        self.random_talk_schedule_file = os.path.join(self.data_dir, 'random_conversation_time.json')
        self.clean_bot_state_file = os.path.join(self.data_dir, 'clean_bot.json')
        
        self._init_json_file(self.discussed_topics_file, {})
        self._init_json_file(self.message_queue_file, [])
        self._init_json_file(self.reaction_log_file, {}) # Initializes the reaction log
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
            if 'queue' in file_path or 'time' in file_path or 'random' in file_path:
                return []
            return {}

    def save_json(self, file_path, data):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    # --- REACTION LOGGING METHODS ---

    # --- NEW METHOD ---
    def has_reacted(self, message_text: str) -> bool:
        """Checks if the bot has already reacted to this exact message text."""
        reaction_log = self.load_json(self.reaction_log_file)
        return message_text in reaction_log

    # --- NEW METHOD ---
    def log_reaction(self, message_text: str):
        """Logs that the bot has reacted to a message to prevent duplicates."""
        reaction_log = self.load_json(self.reaction_log_file)
        # Add the new reaction with a timestamp
        reaction_log[message_text] = get_ist_time()
        
        # To prevent the log from growing forever, keep only the last 200 reactions
        if len(reaction_log) > 200:
            # Sort items by timestamp and keep the most recent 200
            sorted_items = sorted(reaction_log.items(), key=lambda item: item[1], reverse=True)
            reaction_log = dict(sorted_items[:200])

        self.save_json(self.reaction_log_file, reaction_log)

    # --- END OF NEW METHODS ---

    def save_initiation_schedule(self, conversation_dict: dict):
        schedule = {}
        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        sorted_convo = sorted(conversation_dict.items(), key=lambda x: x[1]['delay_minutes'])

        current_time = now
        for persona_name, details in sorted_convo:
            minutes_to_add = details['delay_minutes']
            message_text = details['message']
            telegram_user = details.get('telegram_user')
            
            future_time = now + timedelta(minutes=minutes_to_add)
            schedule_key = future_time.strftime("%Y-%m-%d %H:%M:%S")
            schedule[schedule_key] = [persona_name, message_text, telegram_user]

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
        # Atomically load, pop, and save to prevent race conditions
        message = queue.pop(0)
        self.save_json(self.message_queue_file, queue)
        return message

    def save_error(self, error_traceback: str):
        errors = self.load_json(self.error_file)
        errors[get_ist_time()] = error_traceback
        self.save_json(self.error_file, errors)

    def is_topic_discussed(self, topic: str) -> bool:
        topics = self.load_json(self.discussed_topics_file)
        return topic in topics

    def save_discussed_topic(self, topic: str):
        topics = self.load_json(self.discussed_topics_file)
        topics[topic] = get_ist_time()
        if len(topics) > 50:
            sorted_topics = sorted(topics.items(), key=lambda item: item[1], reverse=True)
            topics = dict(sorted_topics[:50])
        self.save_json(self.discussed_topics_file, topics)

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')