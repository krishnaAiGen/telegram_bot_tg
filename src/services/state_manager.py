# src/services/state_manager.py
import json
import os
import time

from datetime import datetime, timezone

from config.settings import APP_CONFIG

class StateManager:
    """Manages persistent file-based state like logs."""
    def __init__(self):
        self.data_dir = APP_CONFIG['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.processed_log_file = os.path.join(self.data_dir, 'processed_log.json')
        self.initiated_topics_file = os.path.join(self.data_dir, 'initiated_topics.json')
        
        self.bot_state_file = os.path.join(self.data_dir, 'bot_state.json')
          
        self.save_json(self.processed_log_file, {}) 
        self._init_json_file(self.initiated_topics_file, {})
        self._init_json_file(self.bot_state_file, {"last_activity_time": time.time()})


    def _init_json_file(self, file_path, default_content):
        if not os.path.exists(file_path):
            self.save_json(file_path, default_content)

    def load_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save_json(self, file_path, data):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    def load_bot_state(self) -> dict:
        """Loads the bot's core state, providing defaults if missing."""
        state = self.load_json(self.bot_state_file)
        if "last_activity_time" not in state:
            state["last_activity_time"] = time.time()
        return state

    def save_bot_state(self, state: dict):
        """Saves the bot's core state to the file."""
        self.save_json(self.bot_state_file, state)

    def has_processed(self, message_id: int) -> bool:
        log = self.load_json(self.processed_log_file)
        return str(message_id) in log

    def log_processed(self, message_id: int):
        log = self.load_json(self.processed_log_file)
        log[str(message_id)] = datetime.now(timezone.utc).isoformat()
        if len(log) > 500:
            sorted_items = sorted(log.items(), key=lambda item: item[1], reverse=True)
            log = dict(sorted_items[:400])
        self.save_json(self.processed_log_file, log)

    def log_initiated_topic(self, topic: str):
        """Logs a topic that the bot has initiated."""
        topics = self.load_json(self.initiated_topics_file)
        topics[topic] = datetime.now(timezone.utc).isoformat()
        if len(topics) > 50:
            sorted_topics = sorted(topics.items(), key=lambda item: item[1], reverse=True)
            topics = dict(sorted_topics[:40])
        self.save_json(self.initiated_topics_file, topics)

    def is_topic_recently_initiated(self, topic: str) -> bool:
        """Checks if a similar topic has been initiated recently."""
        topics = self.load_json(self.initiated_topics_file)
        return topic.lower() in (t.lower() for t in topics.keys())