# src/processes/telegram_ingestor.py
import asyncio
import os
import firebase_admin
from firebase_admin import credentials, firestore
from telethon import TelegramClient, events

from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services import utils

class DataIngestor:
    def __init__(self):
        self.config = APP_CONFIG
        self.data_dir = utils.get_data_dir(self.config)
        self.brain_queue_path = os.path.join(self.data_dir, 'brain_input_queue.json')
        self.processed_log_path = os.path.join(self.data_dir, 'processed_log.json') # For history check
        
        self.channel_key = self.config.get("telegram_channel")
        self.source_channel = '@' + self.channel_key

        self.flag_file = os.path.join(self.data_dir, "history_fetch_done.txt")
        
        user_key = list(TELEGRAM_USERS.keys())[0]
        user_config = TELEGRAM_USERS[user_key]
        
        session_path = os.path.join(self.data_dir, user_key)
        self.client = TelegramClient(session_path, int(user_config['api_id']), user_config['api_hash'])
        
        # Internal, non-blocking queue to handle incoming events instantly
        self.internal_queue = asyncio.Queue()

        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='data_ingestor_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='data_ingestor_app'))
        self.collection_ref = self.db.collection(f"conversation_ai_{self.channel_key}")

    def _process_and_queue_sync(self, message):
        """A regular, synchronous function to save to Firestore AND queue for the Brain."""
        if not message or not message.text:
            return

        # 1. Save to Firestore for long-term logging
        doc_data = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id, "date": message.date}
        self.collection_ref.document(str(message.id)).set(doc_data)
        print(f"Ingestor: Saved message (ID: {message.id}) to Firestore.")

        # 2. Add to the Brain's input queue file
        brain_message = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id}
        queue = utils.load_json(self.brain_queue_path)
        queue.append(brain_message)
        utils.save_json(self.brain_queue_path, queue)
        print(f"Ingestor: Queued message (ID: {message.id}) for Brain.")

    async def _event_handler(self, event):
        """Extremely fast handler that just puts the message in an internal queue."""
        await self.internal_queue.put(event.message)

    async def _queue_processor(self):
        """Dedicated worker that reads from the internal queue and does the slow database work."""
        print("Ingestor: Queue processor started.")
        while True:
            message = await self.internal_queue.get()
            await asyncio.to_thread(self._process_and_queue_sync, message)
            self.internal_queue.task_done()

    async def _full_history_fetch(self):
        """A one-time operation to fill the Brain's queue with recent messages."""
        print("Ingestor: Performing one-time history check to catch up...")
        processed_log = utils.load_json(self.processed_log_path)
        try:
            async for message in self.client.iter_messages(self.source_channel, limit=50):
                 if message.text and str(message.id) not in processed_log:
                     brain_message = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id}
                     # Just queue it for the brain, no need to re-save to DB
                     queue = utils.load_json(self.brain_queue_path)
                     queue.append(brain_message)
                     utils.save_json(self.brain_queue_path, queue)
                     print(f"Ingestor: Queued historical message (ID: {message.id}) for Brain.")
        except Exception as e:
            print(f"Error during history fetch: {e}")
        
        with open(self.flag_file, "w") as f:
            f.write("done")
        print("Ingestor: History check complete.")

    async def run(self):
        """Main execution method for the DataIngestor."""
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