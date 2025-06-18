import json
import os
from datetime import datetime, timezone

from config.settings import APP_CONFIG

class StateManager:
    """Manages persistent file-based state like logs."""
    def __init__(self):
        self.data_dir = APP_CONFIG['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.processed_log_file = os.path.join(self.data_dir, 'processed_log.json')
        self._init_json_file(self.processed_log_file, {})

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