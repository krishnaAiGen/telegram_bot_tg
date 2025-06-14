# src/ai_controllers/telegram.py
import asyncio
import os
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore
from config import APP_CONFIG, TELEGRAM_USERS

class DataIngestor:
    """
    A standalone process to listen to a Telegram channel and save all messages to Firestore.
    It performs an efficient, one-time full history fetch and then listens for new messages.
    """
    def __init__(self):
        self.config = APP_CONFIG
        self.source_channel = '@' + self.config['source_channel']
        self.flag_file = "fetch_and_save_done.txt"
        
        # Use the first configured user from config as the listener client
        user_key = list(TELEGRAM_USERS.keys())[0]
        user_config = TELEGRAM_USERS[user_key]
        self.client = TelegramClient(user_key, int(user_config['api_id']), user_config['api_hash'])
        
        # Initialize Firebase with a unique app name to avoid conflicts
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='data_ingestor_app')
        
        self.db = firestore.client(app=firebase_admin.get_app(name='data_ingestor_app'))
        self.collection_ref = self.db.collection(f"conversation_ai_{self.config['source_channel']}")

    async def _save_message_to_db(self, message):
        """Saves a single Telethon message object to Firestore."""
        if not message or not message.text:
            return

        doc_ref = self.collection_ref.document(str(message.id))
        doc_data = {
            "message_id": message.id,
            "text": message.text,
            "sender_id": message.sender_id,
            "date": message.date
        }
        # The database set operation must be awaited
        await doc_ref.set(doc_data)
        print(f"Saved message (ID: {message.id}) to Firestore.")

    async def _full_history_fetch_with_batching(self):
        """Performs a one-time fetch of channel history using efficient Firestore batching."""
        print(f"Performing a one-time full history fetch from {self.source_channel}...")
        batch = self.db.batch()
        batch_count = 0
        total_saved = 0

        async for message in self.client.iter_messages(self.source_channel):
            if message and message.text:
                doc_ref = self.collection_ref.document(str(message.id))
                doc_data = {
                    "message_id": message.id, "text": message.text,
                    "sender_id": message.sender_id, "date": message.date
                }
                batch.set(doc_ref, doc_data)
                batch_count += 1
                
                # Firestore batch limit is 500 operations
                if batch_count >= 499:
                    await batch.commit()
                    total_saved += batch_count
                    print(f"Committed batch of {batch_count} messages. Total saved: {total_saved}")
                    batch = self.db.batch()
                    batch_count = 0
        
        if batch_count > 0:
            await batch.commit()
            total_saved += batch_count
            print(f"Committed final batch of {batch_count} messages. Total saved: {total_saved}")

        with open(self.flag_file, "w") as f:
            f.write("Fetch and save complete.")
        print("Full history fetch complete.")

    async def run(self):
        """Main execution method for the DataIngestor."""
        await self.client.start()
        
        if not os.path.exists(self.flag_file):
            await self._full_history_fetch_with_batching()
        else:
            print("Full history fetch already completed. Starting real-time listener.")
        
        # This decorator registers the handler for new messages
        self.client.on(events.NewMessage(chats=[self.source_channel]))(self._save_message_to_db)
        
        print(f"Listening for new messages in {self.source_channel}...")
        await self.client.run_until_disconnected()

if __name__ == "__main__":
    ingestor = DataIngestor()
    asyncio.run(ingestor.run())