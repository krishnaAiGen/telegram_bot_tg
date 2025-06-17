# src/processes/telegram_ingestor.py
import asyncio
import os
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.utils import StateManager

class DataIngestor:
    def __init__(self):
        self.config = APP_CONFIG
        self.state_manager = StateManager()
        channel_key = self.config.get("telegram_channel") or self.config.get("source_channel")
        self.source_channel = '@' + channel_key

        self.flag_file = os.path.join(self.config['data_dir'], "fetch_and_save_done.txt")
        
        user_key = list(TELEGRAM_USERS.keys())[0]
        user_config = TELEGRAM_USERS[user_key]
        
        session_path = os.path.join(self.config['data_dir'], user_key)
        self.client = TelegramClient(session_path, int(user_config['api_id']), user_config['api_hash'])
        
        self.message_queue = asyncio.Queue()

        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='data_ingestor_app')
        
        self.db = firestore.client(app=firebase_admin.get_app(name='data_ingestor_app'))
        self.collection_ref = self.db.collection(f"conversation_ai_{channel_key}")

    def _save_message_sync(self, message):
        if not message or not message.text:
            return
        
        doc_ref = self.collection_ref.document(str(message.id))
        doc_data = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id, "date": message.date}
        doc_ref.set(doc_data)
        print(f"Ingestor: Saved message (ID: {message.id}) to Firestore.")
        
        brain_message = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id}
        self.state_manager.add_message_to_brain_queue(brain_message)
        print(f"Ingestor: Queued message (ID: {message.id}) for Brain.")

    async def _event_handler(self, event):
        await self.message_queue.put(event.message)

    async def _queue_processor(self):
        print("Ingestor: Queue processor started.")
        while True:
            message = await self.message_queue.get()
            await asyncio.to_thread(self._save_message_sync, message)
            self.message_queue.task_done()

    async def _full_history_fetch(self):
        print("Ingestor: Performing one-time history check...")
        try:
            async for message in self.client.iter_messages(self.source_channel, limit=50):
                 if not self.state_manager.has_processed(message.id) and message.text:
                     brain_message = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id}
                     self.state_manager.add_message_to_brain_queue(brain_message)
                     print(f"Ingestor: Queued historical message (ID: {message.id}) for Brain.")
        except Exception as e:
            print(f"Error during history fetch: {e}")
        with open(self.flag_file, "w") as f: f.write("done")
        print("Ingestor: History check complete.")

    async def run(self):
        self.client.add_event_handler(self._event_handler, events.NewMessage(chats=[self.source_channel]))
        await self.client.start()
        
        processor_task = asyncio.create_task(self._queue_processor())
        
        if not os.path.exists(self.flag_file):
            await self._full_history_fetch()
        
        print(f"Ingestor: Listening for new messages in {self.source_channel}...")
        
        try:
            await self.client.run_until_disconnected()
        finally:
            processor_task.cancel()
            await asyncio.gather(processor_task, return_exceptions=True)

if __name__ == "__main__":
    ingestor = DataIngestor()
    asyncio.run(ingestor.run())