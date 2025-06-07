# telegram.py
import asyncio
import os
import json
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore

class DataIngestor:
    """
    A standalone process to listen to a Telegram channel and save all messages to Firestore.
    Preserves the original logic of a one-time full history fetch followed by real-time listening.
    """
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.source_channel = '@' + self.config['source_channel']
        self.flag_file = "fetch_and_save_done.txt"
        
        # Using a hardcoded user from your original code.
        self.user_credentials = {
            "api_id": 23724256,
            "api_hash": "e9e6694fcaa2b502c2d2bbae922e4414"
        }
        self.client = TelegramClient('listener_session', self.user_credentials['api_id'], self.user_credentials['api_hash'])
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred'])
            firebase_admin.initialize_app(cred, name='data_ingestor_app')
        
        self.db = firestore.client(app=firebase_admin.get_app(name='data_ingestor_app'))

    def _get_collection(self, collection_name):
        """Helper method to get the correct Firestore collection reference."""
        sanitized_name = collection_name.lstrip('@')
        final_name = f"conversation_ai_{sanitized_name}"
        return self.db.collection(final_name)

    async def _full_history_fetch(self):
        """Performs a one-time fetch of the channel history using efficient batching."""
        print(f"Performing a one-time full history fetch from {self.source_channel}...")
        collection = self._get_collection(self.source_channel)
        batch = self.db.batch()
        batch_count = 0
        total_saved = 0

        async for message in self.client.iter_messages(self.source_channel):
            if message and message.text:
                doc_ref = collection.document(str(message.id))
                
                # Your original code checked for existence, but for a pure backfill,
                # simply setting the data is more efficient. We will stick to the original logic
                # but make it properly async.
                doc = await doc_ref.get() # CRITICAL FIX: was synchronous, now async
                if not doc.exists:
                    doc_data = {
                        "message_id": message.id, "text": message.text,
                        "sender_id": message.sender_id, "date": message.date
                    }
                    batch.set(doc_ref, doc_data)
                    batch_count += 1
                
                if batch_count >= 499:
                    await batch.commit() # CRITICAL FIX: was synchronous, now async
                    total_saved += batch_count
                    print(f"Committed batch of {batch_count} new messages. Total saved: {total_saved}")
                    batch = self.db.batch()
                    batch_count = 0
        
        if batch_count > 0:
            await batch.commit() # CRITICAL FIX: was synchronous, now async
            total_saved += batch_count
            print(f"Committed final batch of {batch_count} new messages. Total saved: {total_saved}")

        with open(self.flag_file, "w") as f:
            f.write("Fetch and save complete")
        print("Full history fetch complete.")

    async def _start_listener(self):
        """Starts listening for new messages in real-time."""
        @self.client.on(events.NewMessage(chats=[self.source_channel]))
        async def handle_new_message(event):
            print(f"New message received in {self.source_channel}: {event.raw_text}")
            collection = self._get_collection(self.source_channel)
            doc_data = {
                "message_id": event.id, "text": event.raw_text,
                "sender_id": event.sender_id, "date": event.date
            }
            # CRITICAL FIX: The database set operation must be awaited.
            await collection.document(str(event.id)).set(doc_data)
            print(f"Saved new message: {doc_data}")

        print(f"Now listening for new messages in {self.source_channel}...")
        await self.client.run_until_disconnected()

    async def run(self):
        """Main execution method for the DataIngestor."""
        await self.client.start()
        
        if not os.path.exists(self.flag_file):
            await self._full_history_fetch()
        else:
            print("Full history fetch already completed, skipping.")
        
        await self._start_listener()

if __name__ == "__main__":
    ingestor = DataIngestor()
    asyncio.run(ingestor.run())