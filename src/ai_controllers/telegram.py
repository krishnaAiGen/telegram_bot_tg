#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 14 12:06:18 2024

@author: krishnayadav
"""

from telethon import TelegramClient, events
import os
import json
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.retry import Retry


# load_dotenv()

# FIREBASE_CONFIG = json.loads(os.getenv("FIREBASE_APP_CONFIG"))
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

FIREBASE_CONFIG = config['firebase_cred']
cred = credentials.Certificate(FIREBASE_CONFIG)
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_collection(collection_name):
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    return db.collection(final_name)

USERS = {
    "JoiN9911": {
        "api_id": 23724256,
        "api_hash": "e9e6694fcaa2b502c2d2bbae922e4414",
        "username": "JoiN9911",
        "phone_no": "+916299207265"
    }
}

CHANNEL_USERNAME = '@' + config['source_channel']
FLAG_FILE = "fetch_and_save_done.txt"  # File to track if function has been run

clients = {}
for user, config in USERS.items():
    clients[user] = TelegramClient(config["username"], config["api_id"], config["api_hash"])


async def fetch_and_save_channel_messages(client, channel_username):
    await client.start()
    print(f"Fetching all messages from {channel_username}")
    collection = get_collection(channel_username)
    
    # Initialize Firestore batch
    batch = db.batch()
    batch_count = 0  # Keep track of the number of operations in the current batch
    total_count = 0  # Total number of messages processed
    new_messages_count = 0  # Count of new messages added
    
    async for message in client.iter_messages(channel_username):
        if message.text:
            doc_ref = collection.document(str(message.id))
            
            # Check if the document already exists
            doc = doc_ref.get()
            if not doc.exists:
                doc_data = {
                    "message_id": message.id,
                    "text": message.text,
                    "sender_id": message.sender_id,
                    "date": message.date
                }
                batch.set(doc_ref, doc_data)  # Add the operation to the batch
                batch_count += 1
                new_messages_count += 1
                
                # Commit the batch if the limit is reached
                if batch_count == 500:
                    batch.commit()  # Commit the batch to Firestore
                    print(f"Committed 500 new messages to Firestore.")
                    batch = db.batch()  # Start a new batch
                    batch_count = 0
    
    # Commit any remaining operations in the batch
    if batch_count > 0:
        batch.commit()
        print(f"Committed the final {batch_count} new messages to Firestore.")
    
    print(f"Total messages processed: {total_count}")
    print(f"New messages saved: {new_messages_count}")



async def listen_to_channel_messages():
    listening_client = list(clients.values())[0]
    async with listening_client:
        @listening_client.on(events.NewMessage(chats=[CHANNEL_USERNAME]))
        async def handle_new_message(event):
            print(f"New message in {CHANNEL_USERNAME}: {event.raw_text}")
            collection = get_collection(CHANNEL_USERNAME)
            doc_data = {
                "message_id": event.id,
                "text": event.raw_text,
                "sender_id": event.sender_id,
                "date": event.date
            }
            collection.document(str(event.id)).set(doc_data)
            print(f"Saved new message: {doc_data}")

        print(f"Listening for new messages in {CHANNEL_USERNAME}...")
        await listening_client.run_until_disconnected()


async def main():
    # Check if the function has already been run
    if not os.path.exists(FLAG_FILE):
        await fetch_and_save_channel_messages(clients["JoiN9911"], CHANNEL_USERNAME)
        # Create the flag file to indicate the function has been run
        with open(FLAG_FILE, "w") as f:
            f.write("Fetch and save complete")
    else:
        print("Fetch and save operation already completed, skipping.")

    await listen_to_channel_messages()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    
