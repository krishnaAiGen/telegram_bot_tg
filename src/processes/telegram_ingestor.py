# src/processes/telegram_ingestor.py
import asyncio
import os
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import APP_CONFIG, TELEGRAM_USERS

class DataIngestor:
    def __init__(self):
        self.config = APP_CONFIG
        channel_key = self.config.get("telegram_channel") or self.config.get("source_channel")
        self.source_channel = '@' + channel_key

        self.flag_file = os.path.join(self.config['data_dir'], "fetch_and_save_done.txt")
        
        user_key = list(TELEGRAM_USERS.keys())[0]
        user_config = TELEGRAM_USERS[user_key]
        
        session_path = os.path.join(self.config['data_dir'], user_key)
        self.client = TelegramClient(session_path, int(user_config['api_id']), user_config['api_hash'])
        
        # --- NEW: An internal async queue for processing ---
        self.message_queue = asyncio.Queue()

        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='data_ingestor_app')
        
        self.db = firestore.client(app=firebase_admin.get_app(name='data_ingestor_app'))
        self.collection_ref = self.db.collection(f"conversation_ai_{channel_key}")

    def _save_message_sync(self, message):
        """A regular, synchronous function to save a message to Firestore."""
        if not message or not message.text:
            return
        doc_ref = self.collection_ref.document(str(message.id))
        doc_data = {
            "message_id": message.id, "text": message.text,
            "sender_id": message.sender_id, "date": message.date
        }
        doc_ref.set(doc_data)
        print(f"Ingestor: Saved message (ID: {message.id}) to Firestore.")

    async def _event_handler(self, event):
        """
        This handler is SUPER FAST. It just puts the message in the queue and returns.
        """
        await self.message_queue.put(event.message)

    async def _queue_processor(self):
        """
        A dedicated worker that reads from the queue and does the slow database work.
        """
        print("Ingestor: Queue processor started.")
        while True:
            # Wait for a message to appear in the queue
            message = await self.message_queue.get()
            # Run the slow, blocking database function in a background thread
            await asyncio.to_thread(self._save_message_sync, message)
            # Mark the queue item as done
            self.message_queue.task_done()

    async def _full_history_fetch_with_batching(self):
        # This function remains largely the same as it's a one-time operation
        print(f"Ingestor: Performing a one-time full history fetch from {self.source_channel}...")
        batch = self.db.batch()
        batch_count = 0
        total_saved = 0
        async for message in self.client.iter_messages(self.source_channel):
            if message and message.text:
                doc_ref = self.collection_ref.document(str(message.id))
                doc_data = {"message_id": message.id, "text": message.text, "sender_id": message.sender_id, "date": message.date}
                batch.set(doc_data)
                batch_count += 1
                if batch_count >= 499:
                    await asyncio.to_thread(batch.commit)
                    total_saved += batch_count
                    print(f"Ingestor: Committed batch of {batch_count} messages. Total saved: {total_saved}")
                    batch = self.db.batch()
                    batch_count = 0
        if batch_count > 0:
            await asyncio.to_thread(batch.commit)
            total_saved += batch_count
            print(f"Ingestor: Committed final batch of {batch_count} messages. Total saved: {total_saved}")
        with open(self.flag_file, "w") as f: f.write("done")
        print("Ingestor: Full history fetch complete.")

    async def run(self):
        """Main execution method for the DataIngestor."""
        # --- MODIFIED LOGIC ---
        # 1. Register the fast event handler
        self.client.add_event_handler(self._event_handler, events.NewMessage(chats=[self.source_channel]))
        
        await self.client.start()
        
        # 2. Start the background queue processor task
        processor_task = asyncio.create_task(self._queue_processor())
        
        if not os.path.exists(self.flag_file):
            await self._full_history_fetch_with_batching()
        else:
            print("Ingestor: Full history fetch already completed. Starting real-time listener.")
        
        print(f"Ingestor: Listening for new messages in {self.source_channel}...")
        
        # 3. Run until disconnected, and ensure the processor task is handled
        try:
            await self.client.run_until_disconnected()
        finally:
            processor_task.cancel()
            await asyncio.gather(processor_task, return_exceptions=True)

if __name__ == "__main__":
    # Remove the debug print from settings if it's still there
    # from config.settings import APP_CONFIG
    print(f"DEBUG: MIN_REACT_MINS from .env = {os.getenv('MIN_REACT_MINS')}")
    ingestor = DataIngestor()
    asyncio.run(ingestor.run())