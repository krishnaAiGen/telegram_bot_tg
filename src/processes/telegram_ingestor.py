# src/processes/telegram_ingestor.py
import asyncio
import os
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore

# Import from the new, centralized config location
from config.settings import APP_CONFIG, TELEGRAM_USERS

class DataIngestor:
    """
    A standalone process to listen to a Telegram channel and save all messages to Firestore.
    It performs an efficient, one-time full history fetch and then listens for new messages.
    """
    def __init__(self):
        self.config = APP_CONFIG
        self.source_channel = '@' + self.config['source_channel']
        # This flag file is a simple mechanism to ensure the full history is only fetched once.
        self.flag_file = os.path.join(self.config['data_dir'], "fetch_and_save_done.txt")
        
        # Use the first configured user from config as the dedicated listener client.
        user_key = list(TELEGRAM_USERS.keys())[0]
        user_config = TELEGRAM_USERS[user_key]
        
        session_path = os.path.join(self.config['data_dir'], user_key)

        # The Telethon client needs the API ID as an integer.
        self.client = TelegramClient(session_path, int(user_config['api_id']), user_config['api_hash'])
        
        # Initialize Firebase with a unique app name to prevent conflicts with other processes.
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
        # The database `set` operation is an I/O call and must be awaited.
        await doc_ref.set(doc_data)
        print(f"Ingestor: Saved message (ID: {message.id}) to Firestore.")

    async def _full_history_fetch_with_batching(self):
        """Performs a one-time fetch of channel history using efficient Firestore batching."""
        print(f"Ingestor: Performing a one-time full history fetch from {self.source_channel}...")
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
                
                # Firestore batch limit is 500 operations. We commit just below the limit for safety.
                if batch_count >= 499:
                    await batch.commit()
                    total_saved += batch_count
                    print(f"Ingestor: Committed batch of {batch_count} messages. Total saved: {total_saved}")
                    batch = self.db.batch() # Start a new batch
                    batch_count = 0
        
        # Commit any remaining messages in the final batch.
        if batch_count > 0:
            await batch.commit()
            total_saved += batch_count
            print(f"Ingestor: Committed final batch of {batch_count} messages. Total saved: {total_saved}")

        with open(self.flag_file, "w") as f:
            f.write("done")
        print("Ingestor: Full history fetch complete.")

    async def run(self):
        """Main execution method for the DataIngestor."""
        await self.client.start()
        
        # The two-phase startup logic is preserved.
        if not os.path.exists(self.flag_file):
            await self._full_history_fetch_with_batching()
        else:
            print("Ingestor: Full history fetch already completed. Starting real-time listener.")
        
        # This Telethon decorator registers the handler for new messages.
        self.client.on(events.NewMessage(chats=[self.source_channel]))(self._save_message_to_db)
        
        print(f"Ingestor: Listening for new messages in {self.source_channel}...")
        await self.client.run_until_disconnected()

if __name__ == "__main__":
    # This block allows the script to be run directly from the command line.
    ingestor = DataIngestor()
    asyncio.run(ingestor.run())